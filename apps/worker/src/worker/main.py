from datetime import datetime, timezone
from time import sleep


def main() -> None:
    while True:
        now = datetime.now(timezone.utc).isoformat()
        print(f"[worker] heartbeat {now}", flush=True)
        sleep(30)


if __name__ == "__main__":
    main()
