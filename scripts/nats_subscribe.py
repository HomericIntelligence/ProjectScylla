#!/usr/bin/env python3
"""Subscribe to NATS JetStream events from ProjectHermes.

.. deprecated::
    This script is deprecated. Use ``manage_experiment.py subscribe`` instead::

        python scripts/manage_experiment.py subscribe
        python scripts/manage_experiment.py subscribe --config-dir /path/to/project
        NATS_URL=nats://remote:4222 python scripts/manage_experiment.py subscribe

    This standalone script duplicates functionality now provided by the
    ``manage_experiment.py subscribe`` subcommand and will be removed in a future release.

Starts a long-running subscriber that listens for task events on the
``hi.tasks.*`` subject hierarchy. Press Ctrl+C to stop.

Usage:
    python scripts/nats_subscribe.py
    python scripts/nats_subscribe.py --config-dir /path/to/project
    NATS_URL=nats://remote:4222 python scripts/nats_subscribe.py
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import warnings
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Run the NATS subscriber."""
    warnings.warn(
        "nats_subscribe.py is deprecated and will be removed in a future release. "
        "Use 'python scripts/manage_experiment.py subscribe' instead.",
        DeprecationWarning,
        stacklevel=1,
    )
    parser = argparse.ArgumentParser(
        description="Subscribe to NATS JetStream events from ProjectHermes.",
    )
    parser.add_argument(
        "--config-dir",
        default=".",
        help="Project root directory containing config/defaults.yaml (default: .)",
    )
    args = parser.parse_args(argv)

    from scylla.config import ConfigLoader, ConfigurationError

    loader = ConfigLoader(Path(args.config_dir))

    try:
        defaults = loader.load_defaults()
    except ConfigurationError as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    nats_config = defaults.nats

    if not nats_config.enabled:
        print(
            "NATS subscription is disabled in config/defaults.yaml (nats.enabled=false).\n"
            "Set nats.enabled to true or use NATS_URL env var to enable.",
            file=sys.stderr,
        )
        return 1

    try:
        from scylla.nats import NATSSubscriberThread, create_default_router
    except ImportError:
        print(
            "nats-py is not installed. Install with: pip install 'scylla[nats]'",
            file=sys.stderr,
        )
        return 1

    # Configure logging
    log_level = getattr(logging, defaults.logging.level, logging.INFO)
    logging.basicConfig(level=log_level, format=defaults.logging.format)

    router = create_default_router()
    subscriber = NATSSubscriberThread(config=nats_config, handler=router.dispatch)

    stop_event = threading.Event()

    def _signal_handler(signum: int, frame: object) -> None:
        print("\nShutdown requested...")
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print(f"Subscribing to NATS at {nats_config.url} (stream={nats_config.stream})")
    subscriber.start()

    # Block until shutdown signal
    stop_event.wait()

    print("Stopping subscriber...")
    subscriber.stop()
    print("Subscriber stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
