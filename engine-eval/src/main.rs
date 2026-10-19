// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

//! engine-eval: vericto-engine without sockets, for three jobs.
//!
//!   engine-eval export-rules                 the built-in rules as /sync/rules
//!                                            sends them (cpstub serves this file)
//!   engine-eval verdicts FILE [--sensitive S] every statement of `vbench dump`
//!                                            evaluated with the built-in rules and
//!                                            the default policy; exit 1 when a
//!                                            decision differs from the declared verdict
//!   engine-eval bench FILE                   evaluation time per statement class,
//!                                            single thread (p50/p99/p99.9/max, us)
//!
//! FILE: JSON lines with `class`, `dialect` (postgres|mysql), `sql` and
//! `verdict` (allow|flag|block), as printed by `vbench dump`.
use std::io::BufRead;
use std::time::Instant;

use serde_json::{json, Value};
use vericto_engine::{
    evaluate, standard_rules, Decision, Dialect, EnforcementPolicy, Rule, SensitiveColumn,
    ENGINE_VERSION, STANDARD_RULESET_VERSION,
};

fn lower<T: std::fmt::Debug>(v: T) -> String {
    format!("{v:?}").to_ascii_lowercase()
}

fn export_rules() {
    let rules: Vec<Value> = standard_rules()
        .iter()
        .map(|r: &Rule| {
            json!({
                "rule_id": r.rule_id,
                "code": r.code,
                "severity": lower(r.severity),
                "default_action": lower(r.default_action),
                "rule_type": lower(r.rule_type),
                "ast_condition_yaml": r.ast_condition_yaml,
            })
        })
        .collect();
    let out = json!({
        "engine_version": ENGINE_VERSION,
        "ruleset_version": STANDARD_RULESET_VERSION,
        "rule_count": rules.len(),
        "rules": rules,
    });
    println!("{}", serde_json::to_string_pretty(&out).unwrap());
}

struct Stmt {
    class: String,
    dialect: Dialect,
    dialect_name: String,
    sql: String,
    verdict: String,
}

fn read_statements(path: &str) -> Vec<Stmt> {
    let f = std::fs::File::open(path).unwrap_or_else(|e| panic!("open {path}: {e}"));
    let mut out = Vec::new();
    for line in std::io::BufReader::new(f).lines() {
        let line = line.expect("read");
        if line.trim().is_empty() {
            continue;
        }
        let v: Value = serde_json::from_str(&line).expect("JSON line");
        let s = |k: &str| v.get(k).and_then(Value::as_str).unwrap_or("").to_string();
        let dialect_name = s("dialect");
        let dialect = if dialect_name == "mysql" { Dialect::Mysql } else { Dialect::Postgres };
        out.push(Stmt { class: s("class"), dialect, dialect_name, sql: s("sql"), verdict: s("verdict") });
    }
    out
}

fn policy(sensitive: Option<&str>) -> EnforcementPolicy {
    let mut p = EnforcementPolicy::default();
    if let Some(path) = sensitive {
        let b = std::fs::read_to_string(path).unwrap_or_else(|e| panic!("open {path}: {e}"));
        let tags: Vec<SensitiveColumn> = serde_json::from_str(&b).expect("sensitive columns JSON");
        p.sensitive_columns = tags;
    }
    p
}

fn verdicts(path: &str, sensitive: Option<&str>) -> i32 {
    let rules = standard_rules();
    let pol = policy(sensitive);
    let mut bad = 0;
    for s in read_statements(path) {
        let o = evaluate(&s.sql, s.dialect, &rules, &pol);
        let got = match o.decision {
            Decision::Allow => "allow",
            Decision::Flag => "flag",
            Decision::Block => "block",
        };
        let agree = got == s.verdict;
        if !agree {
            bad += 1;
        }
        println!(
            "{}",
            json!({"class": s.class, "dialect": s.dialect_name, "bytes": s.sql.len(), "declared": s.verdict,
                   "decision": got, "rule": o.rule_code, "rewritten": o.rewritten_query.is_some(), "agree": agree})
        );
    }
    println!("{}", json!({"engine_version": ENGINE_VERSION, "rules": rules.len(), "disagreements": bad}));
    if bad > 0 {
        1
    } else {
        0
    }
}

fn pct(sorted: &[f64], p: f64) -> f64 {
    let rank = (p / 100.0) * (sorted.len() - 1) as f64;
    let (lo, hi) = (rank.floor() as usize, rank.ceil() as usize);
    sorted[lo] + (sorted[hi] - sorted[lo]) * (rank - lo as f64)
}

fn env_num<T: std::str::FromStr>(k: &str, d: T) -> T {
    std::env::var(k).ok().and_then(|v| v.parse().ok()).unwrap_or(d)
}

fn bench(path: &str, sensitive: Option<&str>) {
    // Each statement runs ITERS times or until BUDGET_SECS have passed, with at
    // least MIN_ITERS; `n` reports the count.
    let iters: usize = env_num("ITERS", 20_000);
    let budget = std::time::Duration::from_secs(env_num("BUDGET_SECS", 20));
    let min_iters: usize = env_num("MIN_ITERS", 1_000);
    let rules = standard_rules();
    let pol = policy(sensitive);
    for s in read_statements(path) {
        for _ in 0..200 {
            std::hint::black_box(evaluate(&s.sql, s.dialect, &rules, &pol));
        }
        let mut us = Vec::with_capacity(iters);
        let started = Instant::now();
        for i in 0..iters {
            if i >= min_iters && started.elapsed() >= budget {
                break;
            }
            let t = Instant::now();
            std::hint::black_box(evaluate(&s.sql, s.dialect, &rules, &pol));
            us.push(t.elapsed().as_nanos() as f64 / 1000.0);
        }
        us.sort_by(|a, b| a.partial_cmp(b).unwrap());
        println!(
            "{}",
            json!({"class": s.class, "dialect": s.dialect_name, "bytes": s.sql.len(), "n": us.len(),
                   "mean_us": us.iter().sum::<f64>() / us.len() as f64, "p50_us": pct(&us, 50.0),
                   "p99_us": pct(&us, 99.0), "p999_us": pct(&us, 99.9), "max_us": us[us.len() - 1],
                   "engine_version": ENGINE_VERSION, "rules": rules.len()})
        );
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let sensitive = args.iter().position(|a| a == "--sensitive").and_then(|i| args.get(i + 1)).map(String::as_str);
    match args.get(1).map(String::as_str) {
        Some("export-rules") | Some("--export-rules") => export_rules(),
        Some("verdicts") => std::process::exit(verdicts(args.get(2).expect("FILE"), sensitive)),
        Some("bench") => bench(args.get(2).expect("FILE"), sensitive),
        _ => {
            eprintln!("usage: engine-eval export-rules | verdicts FILE [--sensitive S] | bench FILE [--sensitive S]");
            std::process::exit(2);
        }
    }
}
