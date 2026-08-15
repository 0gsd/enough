//! A ~60-line HTTP/1.1 client for exactly one origin: 127.0.0.1.
//!
//! The shell makes three kinds of request — "is anything on this port?",
//! "is the backend up yet?", and "please shut down" — all plaintext, all
//! loopback, all against a server we spawned ourselves. Pulling in a real
//! client crate (and its TLS stack) to do that would be the larger risk.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::time::Duration;

/// Ceiling on the response we'll buffer. Nothing we ask for is big, and a
/// port squatter that streams forever shouldn't be able to wedge us.
const MAX_BODY: usize = 256 * 1024;

pub struct Response {
    pub status: u16,
    pub body: String,
}

pub fn request(
    port: u16,
    method: &str,
    path: &str,
    headers: &[(&str, &str)],
    timeout: Duration,
) -> Option<Response> {
    request_body(port, method, path, headers, None, timeout)
}

/// As `request`, with an optional JSON body — 2b's onboarding proxies
/// `POST /api/model {"cute": …}` through here.
pub fn request_body(
    port: u16,
    method: &str,
    path: &str,
    headers: &[(&str, &str)],
    body: Option<&str>,
    timeout: Duration,
) -> Option<Response> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let mut sock = TcpStream::connect_timeout(&addr, timeout).ok()?;
    sock.set_read_timeout(Some(timeout)).ok()?;
    sock.set_write_timeout(Some(timeout)).ok()?;
    sock.set_nodelay(true).ok();

    // `Connection: close` lets us read to EOF instead of parsing framing.
    let mut req = format!(
        "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\
         Connection: close\r\nAccept: */*\r\nUser-Agent: enough-desktop\r\n"
    );
    for (k, v) in headers {
        req.push_str(&format!("{k}: {v}\r\n"));
    }
    match body {
        Some(b) => {
            req.push_str("Content-Type: application/json\r\n");
            req.push_str(&format!("Content-Length: {}\r\n", b.len()));
        }
        None if method != "GET" => req.push_str("Content-Length: 0\r\n"),
        None => {}
    }
    req.push_str("\r\n");
    if let Some(b) = body {
        req.push_str(b);
    }

    sock.write_all(req.as_bytes()).ok()?;
    sock.flush().ok()?;

    let mut raw: Vec<u8> = Vec::new();
    let mut buf = [0u8; 8192];
    loop {
        match sock.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => {
                raw.extend_from_slice(&buf[..n]);
                if raw.len() >= MAX_BODY {
                    break;
                }
            }
            // A read timeout mid-response still leaves us whatever arrived,
            // which is enough to read the status line.
            Err(_) => break,
        }
    }
    if raw.is_empty() {
        return None;
    }

    let text = String::from_utf8_lossy(&raw).into_owned();
    let (head, body) = match text.find("\r\n\r\n") {
        Some(i) => (text[..i].to_string(), text[i + 4..].to_string()),
        None => (text.clone(), String::new()),
    };
    let status: u16 = head
        .lines()
        .next()?
        .split_whitespace()
        .nth(1)?
        .parse()
        .ok()?;
    Some(Response { status, body })
}

pub fn get(port: u16, path: &str, timeout: Duration) -> Option<Response> {
    request(port, "GET", path, &[], timeout)
}
