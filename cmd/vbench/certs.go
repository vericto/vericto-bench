// SPDX-FileCopyrightText: 2026 Vericto S.A.S.
// SPDX-License-Identifier: Apache-2.0

package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// certs writes a throwaway CA and one server certificate (ECDSA P-256) for the
// TLS cells: every server of the benchmark presents it, clients encrypt without
// verifying (sslmode=require / skip-verify), as the design specifies. The key
// is generated per run and never leaves the run's hosts.
func certs(dir, names string) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	caKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return err
	}
	now := time.Now().Add(-time.Hour)
	ca := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "vericto-bench run CA"},
		NotBefore: now, NotAfter: now.Add(30 * 24 * time.Hour), IsCA: true, BasicConstraintsValid: true,
		KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign}
	caDER, err := x509.CreateCertificate(rand.Reader, ca, ca, &caKey.PublicKey, caKey)
	if err != nil {
		return err
	}
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return err
	}
	srv := &x509.Certificate{SerialNumber: big.NewInt(2), Subject: pkix.Name{CommonName: "vericto-bench"},
		NotBefore: now, NotAfter: now.Add(30 * 24 * time.Hour), KeyUsage: x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
	for _, n := range strings.Split(names, ",") {
		n = strings.TrimSpace(n)
		if ip := net.ParseIP(n); ip != nil {
			srv.IPAddresses = append(srv.IPAddresses, ip)
		} else if n != "" {
			srv.DNSNames = append(srv.DNSNames, n)
		}
	}
	caCert, _ := x509.ParseCertificate(caDER)
	der, err := x509.CreateCertificate(rand.Reader, srv, caCert, &key.PublicKey, caKey)
	if err != nil {
		return err
	}
	pk, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return err
	}
	write := func(name, typ string, b []byte, mode os.FileMode) error {
		return os.WriteFile(filepath.Join(dir, name), pem.EncodeToMemory(&pem.Block{Type: typ, Bytes: b}), mode)
	}
	if err := write("ca.crt", "CERTIFICATE", caDER, 0o644); err != nil {
		return err
	}
	if err := write("server.crt", "CERTIFICATE", der, 0o644); err != nil {
		return err
	}
	return write("server.key", "PRIVATE KEY", pk, 0o600)
}
