// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

// Package db holds one dedicated client connection per session, so vbench
// measures the connection's latency, not a client-side pool queue.
//
// Protocol modes (PostgreSQL, named as pgbench's -M):
//
//	simple    simple query protocol, one Query message, evaluated every time
//	extended  extended protocol with the unnamed statement, re-parsed on every
//	          execution (node-postgres, psycopg3, JDBC below prepareThreshold).
//	          The proxy evaluates every Parse: the conservative case, and the
//	          headline mode.
//	prepared  named statements cached per connection (pgx default, JDBC above
//	          prepareThreshold): evaluated once per connection, so it measures
//	          almost only forwarding.
//
// MySQL:
//
//	text      COM_QUERY with client-side interpolation (mysql2 query(),
//	          Connector/J default). Evaluated every execution.
//	prepare   server-side prepare + execute + close per statement.
//	prepared  server-side prepared statements cached per connection (sysbench's
//	          default).
//
// Ops marked Simple always go as plain text.
package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/vericto/vericto-bench/internal/workload"
)

// Target is where a session connects. The password never travels in a DSN or
// on the command line: it comes from the environment.
type Target struct {
	Host, User, Password, DB string
	Port                     int
	TLS                      bool // require TLS (encrypted, not verified: the benchmark is not about PKI)
	ConnectTimeout           time.Duration
}

// Session is one connection.
type Session interface {
	Run(ctx context.Context, op *workload.Op, engine string, args []any) error
	RunTxn(ctx context.Context, op *workload.Op, engine string, args [][]any) error
	Exec(ctx context.Context, sql string) error
	Scalar(ctx context.Context, sql string) (string, error)
	Close()
}

// NormaliseMode maps aliases (exec, cache) to the canonical names and checks the mode.
func NormaliseMode(engine, mode string) (string, error) {
	m := strings.ToLower(mode)
	switch engine {
	case "pg":
		switch m {
		case "", "extended", "exec":
			return "extended", nil
		case "simple":
			return "simple", nil
		case "prepared", "cache":
			return "prepared", nil
		}
	case "mysql":
		switch m {
		case "", "text":
			return "text", nil
		case "prepare":
			return "prepare", nil
		case "prepared", "cache":
			return "prepared", nil
		}
	default:
		return "", fmt.Errorf("unknown engine %q (pg | mysql)", engine)
	}
	return "", fmt.Errorf("unknown %s mode %q", engine, mode)
}

// IsBlocked reports whether err is vericto-proxy refusing a statement.
func IsBlocked(err error) bool {
	var pe *pgconn.PgError
	if errors.As(err, &pe) {
		return pe.Code == "42501" && strings.Contains(strings.ToUpper(pe.Message+pe.Detail+pe.Hint), "VERICTO")
	}
	var me *mysql.MySQLError
	if errors.As(err, &me) {
		return me.Number == 1142 && strings.Contains(strings.ToUpper(me.Message), "VERICTO")
	}
	return false
}

// Connect opens one session.
func Connect(ctx context.Context, engine string, t Target, mode string) (Session, error) {
	if t.ConnectTimeout <= 0 {
		t.ConnectTimeout = 15 * time.Second
	}
	switch engine {
	case "pg":
		return pgConnect(ctx, t, mode)
	case "mysql":
		return myConnect(ctx, t, mode)
	}
	return nil, fmt.Errorf("unknown engine %q", engine)
}

// ---- PostgreSQL --------------------------------------------------------------

type pgSession struct {
	c    *pgx.Conn
	mode string
}

func pgConnect(ctx context.Context, t Target, mode string) (*pgSession, error) {
	ssl := "disable"
	if t.TLS {
		ssl = "require"
	}
	cfg, err := pgx.ParseConfig(fmt.Sprintf("host=%s port=%d user=%s dbname=%s sslmode=%s connect_timeout=%d application_name=vbench",
		t.Host, t.Port, t.User, t.DB, ssl, int(t.ConnectTimeout.Seconds())))
	if err != nil {
		return nil, err
	}
	cfg.Password = t.Password
	switch mode {
	case "prepared":
		cfg.DefaultQueryExecMode = pgx.QueryExecModeCacheStatement
	case "simple":
		cfg.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol
	default:
		cfg.DefaultQueryExecMode = pgx.QueryExecModeExec
	}
	c, err := pgx.ConnectConfig(ctx, cfg)
	if err != nil {
		return nil, err
	}
	return &pgSession{c: c, mode: mode}, nil
}

func (s *pgSession) query(ctx context.Context, q string, simple bool, args []any) error {
	if simple {
		args = append([]any{pgx.QueryExecModeSimpleProtocol}, args...)
	}
	rows, err := s.c.Query(ctx, q, args...)
	if err != nil {
		return err
	}
	for rows.Next() {
	}
	rows.Close()
	return rows.Err()
}

func (s *pgSession) Run(ctx context.Context, op *workload.Op, engine string, args []any) error {
	return s.query(ctx, op.SQL(engine), op.Simple, args)
}

func (s *pgSession) RunTxn(ctx context.Context, op *workload.Op, engine string, args [][]any) error {
	if err := s.query(ctx, "BEGIN", true, nil); err != nil {
		return err
	}
	for i, q := range op.TxnSQL(engine) {
		if err := s.query(ctx, q, false, args[i]); err != nil {
			_ = s.query(context.Background(), "ROLLBACK", true, nil)
			return err
		}
	}
	return s.query(ctx, "COMMIT", true, nil)
}

func (s *pgSession) Exec(ctx context.Context, q string) error {
	_, err := s.c.Exec(ctx, q, pgx.QueryExecModeSimpleProtocol)
	return err
}

func (s *pgSession) Scalar(ctx context.Context, q string) (string, error) {
	var v any
	if err := s.c.QueryRow(ctx, q, pgx.QueryExecModeSimpleProtocol).Scan(&v); err != nil {
		return "", err
	}
	return fmt.Sprint(v), nil
}

func (s *pgSession) Close() { _ = s.c.Close(context.Background()) }

// ---- MySQL -------------------------------------------------------------------

type mySession struct {
	db    *sql.DB
	c     *sql.Conn
	mode  string
	stmts map[string]*sql.Stmt
}

func myConnect(ctx context.Context, t Target, mode string) (*mySession, error) {
	cfg := mysql.NewConfig()
	cfg.Net = "tcp"
	cfg.Addr = fmt.Sprintf("%s:%d", t.Host, t.Port)
	cfg.User = t.User
	cfg.Passwd = t.Password
	cfg.DBName = t.DB
	cfg.TLSConfig = "false"
	if t.TLS {
		cfg.TLSConfig = "skip-verify"
	}
	cfg.Timeout = t.ConnectTimeout
	cfg.AllowNativePasswords = true
	cfg.InterpolateParams = mode == "text" || mode == ""
	cfg.ParseTime = true
	conn, err := mysql.NewConnector(cfg)
	if err != nil {
		return nil, err
	}
	db := sql.OpenDB(conn)
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	c, err := db.Conn(ctx)
	if err != nil {
		db.Close()
		return nil, err
	}
	return &mySession{db: db, c: c, mode: mode, stmts: map[string]*sql.Stmt{}}, nil
}

func (s *mySession) query(ctx context.Context, q string, simple bool, args []any) error {
	var rows *sql.Rows
	var err error
	if s.mode == "prepared" && !simple {
		st, ok := s.stmts[q]
		if !ok {
			st, err = s.c.PrepareContext(ctx, q)
			if err != nil {
				return err
			}
			s.stmts[q] = st
		}
		rows, err = st.QueryContext(ctx, args...)
	} else {
		rows, err = s.c.QueryContext(ctx, q, args...)
	}
	if err != nil {
		return err
	}
	for rows.Next() {
	}
	rows.Close()
	return rows.Err()
}

func (s *mySession) Run(ctx context.Context, op *workload.Op, engine string, args []any) error {
	return s.query(ctx, op.SQL(engine), op.Simple, args)
}

func (s *mySession) RunTxn(ctx context.Context, op *workload.Op, engine string, args [][]any) error {
	if _, err := s.c.ExecContext(ctx, "BEGIN"); err != nil {
		return err
	}
	for i, q := range op.TxnSQL(engine) {
		if err := s.query(ctx, q, false, args[i]); err != nil {
			_, _ = s.c.ExecContext(context.Background(), "ROLLBACK")
			return err
		}
	}
	_, err := s.c.ExecContext(ctx, "COMMIT")
	return err
}

func (s *mySession) Exec(ctx context.Context, q string) error {
	_, err := s.c.ExecContext(ctx, q)
	return err
}

func (s *mySession) Scalar(ctx context.Context, q string) (string, error) {
	var v sql.NullString
	if err := s.c.QueryRowContext(ctx, q).Scan(&v); err != nil {
		return "", err
	}
	return v.String, nil
}

func (s *mySession) Close() {
	for _, st := range s.stmts {
		st.Close()
	}
	s.c.Close()
	s.db.Close()
}

// ExecOp runs one execution of op with fresh arguments.
func ExecOp(ctx context.Context, s Session, op *workload.Op, engine string, args []any, txnArgs [][]any) error {
	if op.Txn {
		return s.RunTxn(ctx, op, engine, txnArgs)
	}
	return s.Run(ctx, op, engine, args)
}
