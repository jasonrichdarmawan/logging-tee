import logging
from tqdm import tqdm
import time

from logging_tee import setup_logger

from .otherfile import do_something_with_progress, cause_exception

if __name__ == "__main__":
    setup_logger(log_file="output.log", level=logging.DEBUG)
    logger = logging.getLogger()
    logger2 = logging.getLogger("test_logger2")

    for i in tqdm(
        range(2),
        desc="Processing",
    ):
        time.sleep(0.03)
        logger.info("Processing item %d", i)

    for outer_idx in tqdm(
        range(2),
        desc="Outer",
    ):
        for inner_idx in tqdm(
            range(3),
            desc=f"Inner {outer_idx}",
        ):
            time.sleep(0.02)
            if inner_idx % 5 == 0:
                print(f"Nested step outer={outer_idx} inner={inner_idx}")
        logger.info(f"Completed outer={outer_idx}")

    print("from print statement")
    print("multiple lines\nfrom print statement 2")
    logger.debug("Single line")
    logger.debug("Multiple lines:\nnext line")
    logger.debug("Another single line")
    logger.debug("Multiple lines:\n%s", "next line\nnext line 2")
    logger.warning("Warning message\nwith multiple lines\nand should be logged properly.")
    logger.error("Error message\nwith multiple lines\nand should be logged properly.")
    
    logger2.info("Logger2 info message\nwith multiple lines\nand should be logged properly.")
    
    do_something_with_progress()
    cause_exception()