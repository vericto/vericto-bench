// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package workload

import "fmt"

// Datasets vbench can seed. Seeding runs on the direct path, never through a
// proxy, and builds rows server-side (generate_series / recursive CTE) with
// fixed formulas, so the data is deterministic and nothing bulk crosses the
// network. Tier P seeds `pgbench` with `pgbench -i` and `sysbench` with
// `sysbench prepare` (the standard tools); vbench's versions exist for clients
// that cannot run those tools (a Fargate task).
func Datasets() []string { return []string{"orm", "payload", "pgbench", "sysbench"} }

// SeedSQL returns the statements that build a dataset.
func SeedSQL(dataset, engine string, p Params) ([]string, error) {
	switch dataset {
	case "orm":
		return ormSeed(engine), nil
	case "payload":
		return payloadSeed(engine, p.PayloadRowsTotal), nil
	case "pgbench":
		if engine != "pg" {
			return nil, fmt.Errorf("dataset pgbench is PostgreSQL only")
		}
		return pgbenchSeed(p.PgbenchScale), nil
	case "sysbench":
		return sysbenchSeed(engine, p.SysbenchTables, p.SysbenchRows), nil
	}
	return nil, fmt.Errorf("unknown dataset %q", dataset)
}

// DropSQL removes the vbench schema (orm and payload datasets).
func DropSQL(engine string) []string {
	if engine == "pg" {
		return []string{"DROP SCHEMA IF EXISTS vbench CASCADE"}
	}
	return []string{"DROP DATABASE IF EXISTS vbench"}
}

// ChecksumSQL returns one statement per dataset whose single value fingerprints
// the seeded data (row counts and an md5 over a fixed sample), recorded in the
// manifest so a run on different data is detectable.
func ChecksumSQL(dataset, engine string) string {
	switch dataset {
	case "orm":
		if engine == "pg" {
			return "SELECT (SELECT count(*) FROM vbench.users) || ':' || (SELECT count(*) FROM vbench.orders) || ':' || (SELECT count(*) FROM vbench.order_items) || ':' || (SELECT md5(string_agg(email, ',' ORDER BY id)) FROM vbench.users WHERE id % 997 = 0)"
		}
		return "SELECT CONCAT((SELECT COUNT(*) FROM vbench.users), ':', (SELECT COUNT(*) FROM vbench.orders), ':', (SELECT COUNT(*) FROM vbench.order_items), ':', (SELECT MD5(GROUP_CONCAT(email ORDER BY id SEPARATOR ',')) FROM vbench.users WHERE id % 997 = 0))"
	case "payload":
		if engine == "pg" {
			return "SELECT (SELECT count(*) FROM vbench.payload) || ':' || (SELECT md5(string_agg(payload, '' ORDER BY id)) FROM vbench.payload WHERE id % 1009 = 0)"
		}
		return "SELECT CONCAT((SELECT COUNT(*) FROM vbench.payload), ':', (SELECT MD5(GROUP_CONCAT(payload ORDER BY id SEPARATOR '')) FROM vbench.payload WHERE id % 1009 = 0))"
	case "pgbench":
		return "SELECT (SELECT count(*) FROM pgbench_accounts) || ':' || (SELECT count(*) FROM pgbench_branches) || ':' || (SELECT sum(abalance) FROM pgbench_accounts WHERE aid % 9973 = 0)"
	case "sysbench":
		if engine == "pg" {
			return "SELECT (SELECT count(*) FROM sbtest1) || ':' || (SELECT sum(k) FROM sbtest1 WHERE id % 9973 = 0)"
		}
		return "SELECT CONCAT((SELECT COUNT(*) FROM sbtest1), ':', (SELECT SUM(k) FROM sbtest1 WHERE id % 9973 = 0))"
	}
	return ""
}

func ormSeed(engine string) []string {
	if engine == "pg" {
		return []string{
			"DROP SCHEMA IF EXISTS vbench CASCADE",
			"CREATE SCHEMA vbench",
			"CREATE TABLE vbench.users (id bigint PRIMARY KEY, name text NOT NULL, email text NOT NULL, active boolean NOT NULL DEFAULT true, country text, last_seen timestamptz, created_at timestamptz NOT NULL DEFAULT now())",
			"CREATE TABLE vbench.categories (id int PRIMARY KEY, name text NOT NULL)",
			"CREATE TABLE vbench.products (id bigint PRIMARY KEY, name text NOT NULL, price numeric(10,2) NOT NULL, stock int NOT NULL, category_id int NOT NULL)",
			"CREATE TABLE vbench.orders (id bigserial PRIMARY KEY, user_id bigint NOT NULL, status text NOT NULL, total numeric(10,2) NOT NULL, created_at timestamptz NOT NULL DEFAULT now())",
			"CREATE TABLE vbench.order_items (id bigserial PRIMARY KEY, order_id bigint NOT NULL, product_id bigint NOT NULL, qty int NOT NULL, price numeric(10,2) NOT NULL)",
			"CREATE TABLE vbench.events (id bigserial PRIMARY KEY, user_id bigint NOT NULL, kind text NOT NULL, payload text, created_at timestamptz NOT NULL DEFAULT now())",
			"CREATE TABLE vbench.scratch (id int PRIMARY KEY, n int)",
			"CREATE TABLE vbench.customers_masked (id bigint PRIMARY KEY, name text NOT NULL, email text NOT NULL)",
			"INSERT INTO vbench.categories SELECT g, 'category ' || g FROM generate_series(1::bigint, 20) g",
			fmt.Sprintf("INSERT INTO vbench.users (id, name, email, country, created_at) SELECT g, 'user ' || g, 'user' || g || '@example.com', (ARRAY['US','MX','BR','ES','CO'])[1 + g %% 5], now() - (g %% 900) * interval '1 day' FROM generate_series(1::bigint, %d) g", nUsers),
			fmt.Sprintf("INSERT INTO vbench.products SELECT g, 'product ' || g, round((5 + (g * 37) %% 500)::numeric, 2), 1000000, 1 + g %% 20 FROM generate_series(1::bigint, %d) g", nProducts),
			fmt.Sprintf("INSERT INTO vbench.orders (user_id, status, total, created_at) SELECT 1 + (g * 7919) %% %d, (ARRAY['pending','paid','shipped','delivered','refunded'])[1 + g %% 5], round(((g * 131) %% 50000 / 100.0)::numeric, 2), now() - ((g * 17) %% 129600) * interval '1 minute' FROM generate_series(1::bigint, %d) g", nUsers, nOrders),
			fmt.Sprintf("INSERT INTO vbench.order_items (order_id, product_id, qty, price) SELECT 1 + (g / 3), 1 + (g * 104729) %% %d, 1 + g %% 4, round((5 + (g * 37) %% 500)::numeric, 2) FROM generate_series(0::bigint, %d) g", nProducts, nOrderItems-1),
			fmt.Sprintf("INSERT INTO vbench.customers_masked SELECT g, 'customer ' || g, 'customer' || g || '@example.com' FROM generate_series(1::bigint, %d) g", nCustomers),
			"CREATE INDEX ON vbench.orders (user_id, created_at)",
			"CREATE INDEX ON vbench.orders (created_at)",
			"CREATE INDEX ON vbench.order_items (order_id)",
			"ANALYZE vbench.users", "ANALYZE vbench.products", "ANALYZE vbench.orders", "ANALYZE vbench.order_items",
		}
	}
	gen := func(n int) string {
		return fmt.Sprintf("WITH RECURSIVE s(g) AS (SELECT 1 UNION ALL SELECT g + 1 FROM s WHERE g < %d) ", n)
	}
	return []string{
		"DROP DATABASE IF EXISTS vbench",
		"CREATE DATABASE vbench",
		"SET SESSION cte_max_recursion_depth = 1000000",
		"CREATE TABLE vbench.users (id BIGINT PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(150) NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE, country CHAR(2), last_seen TIMESTAMP NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)",
		"CREATE TABLE vbench.categories (id INT PRIMARY KEY, name VARCHAR(100) NOT NULL)",
		"CREATE TABLE vbench.products (id BIGINT PRIMARY KEY, name VARCHAR(100) NOT NULL, price DECIMAL(10,2) NOT NULL, stock INT NOT NULL, category_id INT NOT NULL)",
		"CREATE TABLE vbench.orders (id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT NOT NULL, status VARCHAR(20) NOT NULL, total DECIMAL(10,2) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, KEY (user_id, created_at), KEY (created_at))",
		"CREATE TABLE vbench.order_items (id BIGINT AUTO_INCREMENT PRIMARY KEY, order_id BIGINT NOT NULL, product_id BIGINT NOT NULL, qty INT NOT NULL, price DECIMAL(10,2) NOT NULL, KEY (order_id))",
		"CREATE TABLE vbench.events (id BIGINT AUTO_INCREMENT PRIMARY KEY, user_id BIGINT NOT NULL, kind VARCHAR(20) NOT NULL, payload TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)",
		"CREATE TABLE vbench.scratch (id INT PRIMARY KEY, n INT)",
		"CREATE TABLE vbench.customers_masked (id BIGINT PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(150) NOT NULL)",
		"INSERT INTO vbench.categories " + gen(20) + "SELECT g, CONCAT('category ', g) FROM s",
		fmt.Sprintf("INSERT INTO vbench.users (id, name, email, country, created_at) %sSELECT g, CONCAT('user ', g), CONCAT('user', g, '@example.com'), ELT(1 + g %% 5, 'US','MX','BR','ES','CO'), NOW() - INTERVAL (g %% 900) DAY FROM s", gen(nUsers)),
		fmt.Sprintf("INSERT INTO vbench.products %sSELECT g, CONCAT('product ', g), 5 + (g * 37) %% 500, 1000000, 1 + g %% 20 FROM s", gen(nProducts)),
		fmt.Sprintf("INSERT INTO vbench.orders (user_id, status, total, created_at) %sSELECT 1 + (g * 7919) %% %d, ELT(1 + g %% 5, 'pending','paid','shipped','delivered','refunded'), ((g * 131) %% 50000) / 100.0, NOW() - INTERVAL ((g * 17) %% 129600) MINUTE FROM s", gen(nOrders), nUsers),
		fmt.Sprintf("INSERT INTO vbench.order_items (order_id, product_id, qty, price) %sSELECT 1 + ((g - 1) DIV 3), 1 + (g * 104729) %% %d, 1 + g %% 4, 5 + (g * 37) %% 500 FROM s", gen(nOrderItems), nProducts),
		fmt.Sprintf("INSERT INTO vbench.customers_masked %sSELECT g, CONCAT('customer ', g), CONCAT('customer', g, '@example.com') FROM s", gen(nCustomers)),
		"ANALYZE TABLE vbench.users, vbench.products, vbench.orders, vbench.order_items",
	}
}

// payloadSeed builds vbench.payload and vbench.payload_m: identical rows of an
// id, a 24-byte email and 1,000 bytes of md5 hex (incompressible enough that
// neither TOAST nor InnoDB compression changes the bytes on the wire).
// Requires the orm dataset's schema/database to exist.
func payloadSeed(engine string, rows int) []string {
	if rows <= 0 {
		rows = 10_000
	}
	if engine == "pg" {
		var out []string
		for _, t := range []string{"vbench.payload", "vbench.payload_m"} {
			out = append(out,
				"DROP TABLE IF EXISTS "+t,
				"CREATE TABLE "+t+" (id bigint PRIMARY KEY, email text NOT NULL, payload text NOT NULL)",
				"ALTER TABLE "+t+" ALTER COLUMN payload SET STORAGE EXTERNAL",
				fmt.Sprintf("INSERT INTO %s SELECT g, 'p' || lpad(g::text, 7, '0') || '@example.com', substr(repeat(md5(g::text) || md5((g + 1)::text), 16), 1, 1000) FROM generate_series(1::bigint, %d) g", t, rows),
				"ANALYZE "+t)
		}
		return out
	}
	var out []string
	out = append(out, "SET SESSION cte_max_recursion_depth = 1000000")
	for _, t := range []string{"vbench.payload", "vbench.payload_m"} {
		out = append(out,
			"DROP TABLE IF EXISTS "+t,
			"CREATE TABLE "+t+" (id BIGINT PRIMARY KEY, email VARCHAR(64) NOT NULL, payload TEXT NOT NULL)",
			fmt.Sprintf("INSERT INTO %s WITH RECURSIVE s(g) AS (SELECT 1 UNION ALL SELECT g + 1 FROM s WHERE g < %d) SELECT g, CONCAT('p', LPAD(g, 7, '0'), '@example.com'), SUBSTRING(REPEAT(CONCAT(MD5(g), MD5(g + 1)), 16), 1, 1000) FROM s", t, rows),
			"ANALYZE TABLE "+t)
	}
	return out
}

// pgbenchSeed builds the pgbench schema as `pgbench -i -s scale` does
// (same tables, row counts and filler widths; abalance starts at 0).
func pgbenchSeed(scale int) []string {
	if scale <= 0 {
		scale = 1
	}
	return []string{
		"DROP TABLE IF EXISTS pgbench_accounts, pgbench_branches, pgbench_tellers, pgbench_history",
		"CREATE TABLE pgbench_history (tid int, bid int, aid int, delta int, mtime timestamp, filler char(22))",
		"CREATE TABLE pgbench_tellers (tid int NOT NULL, bid int, tbalance int, filler char(84)) WITH (fillfactor = 100)",
		"CREATE TABLE pgbench_accounts (aid int NOT NULL, bid int, abalance int, filler char(84)) WITH (fillfactor = 100)",
		"CREATE TABLE pgbench_branches (bid int NOT NULL, bbalance int, filler char(88)) WITH (fillfactor = 100)",
		fmt.Sprintf("INSERT INTO pgbench_branches (bid, bbalance) SELECT g, 0 FROM generate_series(1, %d) g", scale),
		fmt.Sprintf("INSERT INTO pgbench_tellers (tid, bid, tbalance) SELECT g, (g - 1) / 10 + 1, 0 FROM generate_series(1, %d) g", 10*scale),
		fmt.Sprintf("INSERT INTO pgbench_accounts (aid, bid, abalance, filler) SELECT g, (g - 1) / 100000 + 1, 0, '' FROM generate_series(1, %d) g", 100000*scale),
		"ALTER TABLE pgbench_branches ADD PRIMARY KEY (bid)",
		"ALTER TABLE pgbench_tellers ADD PRIMARY KEY (tid)",
		"ALTER TABLE pgbench_accounts ADD PRIMARY KEY (aid)",
		"VACUUM ANALYZE pgbench_branches", "VACUUM ANALYZE pgbench_tellers", "VACUUM ANALYZE pgbench_accounts",
	}
}

// sysbenchSeed builds sbtest1..N like `sysbench oltp_common prepare`, with a
// deterministic k and c instead of sysbench's random strings.
func sysbenchSeed(engine string, tables, rows int) []string {
	if tables <= 0 {
		tables = 1
	}
	if rows <= 0 {
		rows = 10000
	}
	var out []string
	if engine == "mysql" {
		out = append(out, "SET SESSION cte_max_recursion_depth = 10000000")
	}
	for t := 1; t <= tables; t++ {
		tbl := fmt.Sprintf("sbtest%d", t)
		if engine == "pg" {
			out = append(out,
				"DROP TABLE IF EXISTS "+tbl,
				"CREATE TABLE "+tbl+" (id serial PRIMARY KEY, k integer NOT NULL DEFAULT 0, c char(120) NOT NULL DEFAULT '', pad char(60) NOT NULL DEFAULT '')",
				fmt.Sprintf("INSERT INTO %s (k, c, pad) SELECT 1 + (g * 7919) %% %d, rpad(md5(g::text) || md5((g * 3)::text) || md5((g * 7)::text), 119), rpad(md5((g * 11)::text), 59) FROM generate_series(1, %d) g", tbl, rows, rows),
				fmt.Sprintf("CREATE INDEX k_%d ON %s (k)", t, tbl),
				"ANALYZE "+tbl)
			continue
		}
		out = append(out,
			"DROP TABLE IF EXISTS "+tbl,
			"CREATE TABLE "+tbl+" (id INTEGER NOT NULL AUTO_INCREMENT, k INTEGER NOT NULL DEFAULT 0, c CHAR(120) NOT NULL DEFAULT '', pad CHAR(60) NOT NULL DEFAULT '', PRIMARY KEY (id)) ENGINE=InnoDB",
			fmt.Sprintf("INSERT INTO %s (k, c, pad) WITH RECURSIVE s(g) AS (SELECT 1 UNION ALL SELECT g + 1 FROM s WHERE g < %d) SELECT 1 + (g * 7919) %% %d, RPAD(CONCAT(MD5(g), MD5(g * 3), MD5(g * 7)), 119, ' '), RPAD(MD5(g * 11), 59, ' ') FROM s", tbl, rows, rows),
			fmt.Sprintf("CREATE INDEX k_%d ON %s (k)", t, tbl),
			"ANALYZE TABLE "+tbl)
	}
	return out
}
