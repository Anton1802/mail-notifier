import logging

logger = logging.getLogger(__name__)
_format = "%(asctime)s %(levelname)s %(message)s"


def main():
    logging.basicConfig(level=logging.INFO, filename="main.log", format=_format)
    logger.info("Mail notifier started")


if __name__ == "__main__":
    main()
