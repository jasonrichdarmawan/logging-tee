from argparse import ArgumentParser
import logging
from tqdm import tqdm
import time

from .otherfile import do_something_with_progress, cause_exception

if __name__ == "__main__":
    logger = logging.getLogger()
    logger2 = logging.getLogger("test_logger2")

    parser = ArgumentParser(description="Demonstration of logging_tee features.")
    parser.add_argument("--random-arg", type=str, help="A random argument for demonstration purposes.")
    args = parser.parse_args()
    print(f"Random argument received: {args.random_arg}")

    # demonstrate tqdm pbar
    total = 17
    batch_size = 16
    pbar = tqdm(total=total, desc="Overall Progress")
    for i in range(0, total, batch_size):
        time.sleep(2)
        pbar.update(batch_size)
    pbar.close()
    
    # demonstrate tqdm pbar with dynamic postfix
    additional_info = 2
    pbar = tqdm(range(3), total=3, desc="Outer Progress")
    for i in pbar:
        time.sleep(2)
        additional_info *= 2
        pbar.set_postfix({
            "additional_info": f"{additional_info}",
            "more_info": f"{additional_info * 2}",
        })

    # demonstrate nested tqdm pbar
    for i in tqdm(
        range(2),
        desc="Processing",
    ):
        time.sleep(2)
        logger.info("Processing item %d", i)

    for outer_idx in tqdm(
        range(2),
        desc="Outer",
    ):
        time.sleep(2)
        for inner_idx in tqdm(
            range(3),
            desc=f"Inner {outer_idx}",
        ):
            time.sleep(2)
            if inner_idx % 5 == 0:
                print(f"Nested step outer={outer_idx} inner={inner_idx}")
        logger.info(f"Completed outer={outer_idx}")

    # demonstrate logging with multiple lines
    print("from print statement")
    print("multiple lines\nfrom print statement 2")
    logger.debug("Single line")
    logger.debug("Multiple lines:\nnext line")
    logger.debug("Another single line")
    logger.debug("Multiple lines:\n%s", "next line\nnext line 2")
    logger.warning("Warning message\nwith multiple lines\nand should be logged properly.")
    logger.error("Error message\nwith multiple lines\nand should be logged properly.")
    
    # demonstrate using a second logger
    logger2.info("Logger2 info message\nwith multiple lines\nand should be logged properly.")
    
    # demonstrate running logger in other file
    do_something_with_progress()
    cause_exception()