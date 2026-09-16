#!/usr/bin/env python3
"""Run the existing reconciliation guard under the three-region/39-source policy."""
import validate_reconciliation_policy as base

base.POLICY = "stable-id-39-v3-metro-central-90d"

if __name__ == "__main__":
    base.main()
