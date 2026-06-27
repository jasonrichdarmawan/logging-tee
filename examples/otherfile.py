from tqdm import tqdm
import time
import logging

logger = logging.getLogger(__name__)

def do_something_with_progress():
    for i in tqdm(range(2), desc="Processing items"):
        time.sleep(0.03)
        logger.info("Processing item %d", i)
        
def cause_exception():
    raise ValueError("This is an error message\nwith multiple lines\nand should be logged properly.")