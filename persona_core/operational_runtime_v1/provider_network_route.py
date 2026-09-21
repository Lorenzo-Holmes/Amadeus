"""Versioned DeepSeek-only routing. Never mutates process or OS proxy settings."""
from __future__ import annotations
import urllib.request
from transcript_store import ensure

VERSION = 'apcore-network-route-1'
HOST = 'api.deepseek.com'
MODES = frozenset({'SYSTEM_PROXY', 'DIRECT_NO_PROXY'})


def check_route_policy(policy):
    ensure(isinstance(policy, dict) and set(policy) == {'version', 'mode', 'host'},
           'NETWORK_ROUTE_POLICY_SHAPE')
    ensure(policy['version'] == VERSION, 'NETWORK_ROUTE_POLICY_VERSION')
    ensure(policy['host'] == HOST, 'NETWORK_ROUTE_HOST_NOT_ALLOWED')
    ensure(isinstance(policy['mode'], str) and policy['mode'] in MODES, 'NETWORK_ROUTE_MODE')


def proxy_handler(policy):
    check_route_policy(policy)
    # An explicit empty mapping suppresses environment and Windows discovery.
    # This handler is attached only to a local opener for the fixed API host.
    return (urllib.request.ProxyHandler({}) if policy['mode'] == 'DIRECT_NO_PROXY'
            else urllib.request.ProxyHandler())
