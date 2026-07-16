# Features

Supported libraries: [tqdm](https://github.com/tqdm/tqdm), [vLLM](https://github.com/vllm-project/vllm).

Cleanly store tqdm progress bar in human readable format.

```bash
2026-06-27 16:42:16,279 root INFO      Processing item 0
2026-06-27 16:42:16,310 root INFO      Processing item 1
2026-06-27 16:42:16,310 __main__ INFO      tqdm[Processing] done: 2/2 (100.0%), elapsed 0.1s, 32.77 it/s, ETA 0.0s
2026-06-27 16:42:16,331 root INFO      Nested step outer=0 inner=0
2026-06-27 16:42:16,373 __main__ INFO      tqdm[Inner 0] done: 3/3 (100.0%), elapsed 0.1s, 48.82 it/s, ETA 0.0s
2026-06-27 16:42:16,373 root INFO      Completed outer=0
2026-06-27 16:42:16,393 root INFO      Nested step outer=1 inner=0
2026-06-27 16:42:16,434 __main__ INFO      tqdm[Inner 1] done: 3/3 (100.0%), elapsed 0.1s, 49.61 it/s, ETA 0.0s
2026-06-27 16:42:16,435 root INFO      Completed outer=1
2026-06-27 16:42:16,436 __main__ INFO      tqdm[Outer] progress: 2/2 (100.0%), elapsed 0.1s, 16.04 it/s, ETA 0.0s
2026-06-27 16:42:16,436 __main__ INFO      tqdm[Outer] done: 2/2 (100.0%), elapsed 0.1s, 16.04 it/s, ETA 0.0s
```

Find out where the logger is called

```bash
2026-06-27 16:42:16,470 examples.otherfile INFO      Processing item 0
2026-06-27 16:42:16,501 examples.otherfile INFO      Processing item 1
2026-06-27 16:42:16,501 examples.otherfile INFO      tqdm[Processing items] done: 2/2 (100.0%), elapsed 0.1s, 32.98 it/s, ETA 0.0s
```

Only print and store log from specific logger (if do `setup_logger(name="specific logger")`)

```bash
2026-06-27 16:42:16,439 test_logger2 INFO      Logger2 info message
2026-06-27 16:42:16,439 test_logger2 INFO      with multiple lines
2026-06-27 16:42:16,439 test_logger2 INFO      and should be logged properly.
```

# Installation

```bash
pip install logging-tee
```

# Usage

## Run an existing Python program without modifying it

After installing the package, launch a Python command through `logging-tee`:

```bash
logging-tee python demo.py
```

This creates a timestamped log such as `20260714-153045.log` in the current
directory. The launcher configures logging before the target Python program
starts, and captures stdout, stderr, standard `logging` records, and `tqdm`
progress snapshots. The target program's exit status is preserved.

Use `--log-file` to choose the destination and `--level` to set the minimum
stored logging level:

```bash
logging-tee --log-file logs/demo.log --level DEBUG python demo.py --option value
```

Executable shell scripts are supported too. Shell output is recorded, and any
Python process the script starts inherits the logging setup:

```bash
logging-tee --log-file output_cli.log --level DEBUG ./examples/bash_cli.sh --random-arg test
```

For direct Python commands, the launcher configures logging before the program
is imported or executed.

## Configure logging from Python

### Basic usage

```python
import logging
from argparse import ArgumentParser

from logging_tee import setup_logger

if __name__ == "__main__":
    setup_logger(log_file="output.log", level=logging.DEBUG)
    logger = logging.getLogger()

    logger.info("hello world")
```

### Advanced usage

```python
import logging
from tqdm import tqdm
import time
from argparse import ArgumentParser

from logging_tee import setup_logger

from .otherfile import do_something_with_progress, cause_exception

if __name__ == "__main__":
    setup_logger(log_file="output.log", level=logging.DEBUG)
    logger = logging.getLogger()
    logger2 = logging.getLogger("test_logger2")

    parser = ArgumentParser(description="Demonstration of logging_tee features.")
    parser.add_argument("--random-arg", type=str, help="A random argument for demonstration purposes.")
    args = parser.parse_args()
    logger.info("Random argument received: %s", args.random_arg)
    
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
```

output.log
```bash
2026-07-14 22:26:43,586 root INFO      Random argument received: test
2026-07-14 22:26:45,591 __main__ INFO      tqdm[Overall Progress] progress: 16/17 (94.1%), elapsed 2.0s, 7.99 it/s, ETA 0.1s
2026-07-14 22:26:47,593 __main__ INFO      tqdm[Overall Progress] progress: 17/17 (100.0%), elapsed 4.0s, 7.99 it/s, ETA 0.0s
2026-07-14 22:26:47,593 __main__ INFO      tqdm[Overall Progress] done: 17/17 (100.0%), elapsed 4.0s, 7.99 it/s, ETA 0.0s
2026-07-14 22:26:49,597 __main__ INFO      tqdm[Outer Progress] progress: 1/3 (33.3%), elapsed 2.0s, 0.50 it/s, ETA 4.0s, additional_info=4, more_info=8
2026-07-14 22:26:51,601 __main__ INFO      tqdm[Outer Progress] progress: 2/3 (66.7%), elapsed 4.0s, 0.50 it/s, ETA 2.0s, additional_info=8, more_info=16
2026-07-14 22:26:53,604 __main__ INFO      tqdm[Outer Progress] progress: 3/3 (100.0%), elapsed 6.0s, 0.50 it/s, ETA 0.0s, additional_info=16, more_info=32
2026-07-14 22:26:53,605 __main__ INFO      tqdm[Outer Progress] done: 3/3 (100.0%), elapsed 6.0s, 0.50 it/s, ETA 0.0s, additional_info=16, more_info=32
2026-07-14 22:26:55,609 root INFO      Processing item 0
2026-07-14 22:26:55,610 __main__ INFO      tqdm[Processing] progress: 1/2 (50.0%), elapsed 2.0s, 0.50 it/s, ETA 2.0s
2026-07-14 22:26:57,613 root INFO      Processing item 1
2026-07-14 22:26:57,614 __main__ INFO      tqdm[Processing] progress: 2/2 (100.0%), elapsed 4.0s, 0.50 it/s, ETA 0.0s
2026-07-14 22:26:57,615 __main__ INFO      tqdm[Processing] done: 2/2 (100.0%), elapsed 4.0s, 0.50 it/s, ETA 0.0s
2026-07-14 22:27:01,618 root INFO      Nested step outer=0 inner=0
2026-07-14 22:27:01,619 __main__ INFO      tqdm[Inner 0] progress: 1/3 (33.3%), elapsed 2.0s, 0.50 it/s, ETA 4.0s
2026-07-14 22:27:03,622 __main__ INFO      tqdm[Inner 0] progress: 2/3 (66.7%), elapsed 4.0s, 0.50 it/s, ETA 2.0s
2026-07-14 22:27:05,625 __main__ INFO      tqdm[Inner 0] progress: 3/3 (100.0%), elapsed 6.0s, 0.50 it/s, ETA 0.0s
2026-07-14 22:27:05,626 __main__ INFO      tqdm[Inner 0] done: 3/3 (100.0%), elapsed 6.0s, 0.50 it/s, ETA 0.0s
2026-07-14 22:27:05,626 root INFO      Completed outer=0
2026-07-14 22:27:05,626 __main__ INFO      tqdm[Outer] progress: 1/2 (50.0%), elapsed 8.0s, 0.12 it/s, ETA 8.0s
2026-07-14 22:27:09,632 root INFO      Nested step outer=1 inner=0
2026-07-14 22:27:09,633 __main__ INFO      tqdm[Inner 1] progress: 1/3 (33.3%), elapsed 2.0s, 0.50 it/s, ETA 4.0s
2026-07-14 22:27:11,636 __main__ INFO      tqdm[Inner 1] progress: 2/3 (66.7%), elapsed 4.0s, 0.50 it/s, ETA 2.0s
2026-07-14 22:27:13,638 __main__ INFO      tqdm[Inner 1] progress: 3/3 (100.0%), elapsed 6.0s, 0.50 it/s, ETA 0.0s
2026-07-14 22:27:13,639 __main__ INFO      tqdm[Inner 1] done: 3/3 (100.0%), elapsed 6.0s, 0.50 it/s, ETA 0.0s
2026-07-14 22:27:13,640 root INFO      Completed outer=1
2026-07-14 22:27:13,641 __main__ INFO      tqdm[Outer] progress: 2/2 (100.0%), elapsed 16.0s, 0.12 it/s, ETA 0.0s
2026-07-14 22:27:13,641 __main__ INFO      tqdm[Outer] done: 2/2 (100.0%), elapsed 16.0s, 0.12 it/s, ETA 0.0s
2026-07-14 22:27:13,642 root INFO      from print statement
2026-07-14 22:27:13,642 root INFO      multiple lines
2026-07-14 22:27:13,642 root INFO      from print statement 2
2026-07-14 22:27:13,643 root DEBUG     Single line
2026-07-14 22:27:13,643 root DEBUG     Multiple lines:
2026-07-14 22:27:13,643 root DEBUG     next line
2026-07-14 22:27:13,643 root DEBUG     Another single line
2026-07-14 22:27:13,643 root DEBUG     Multiple lines:
2026-07-14 22:27:13,643 root DEBUG     next line
2026-07-14 22:27:13,643 root DEBUG     next line 2
2026-07-14 22:27:13,644 root WARNING   Warning message
2026-07-14 22:27:13,644 root WARNING   with multiple lines
2026-07-14 22:27:13,644 root WARNING   and should be logged properly.
2026-07-14 22:27:13,644 root ERROR     Error message
2026-07-14 22:27:13,644 root ERROR     with multiple lines
2026-07-14 22:27:13,644 root ERROR     and should be logged properly.
2026-07-14 22:27:13,644 test_logger2 INFO      Logger2 info message
2026-07-14 22:27:13,644 test_logger2 INFO      with multiple lines
2026-07-14 22:27:13,644 test_logger2 INFO      and should be logged properly.
2026-07-14 22:27:13,675 examples.otherfile INFO      Processing item 0
2026-07-14 22:27:13,706 examples.otherfile INFO      Processing item 1
2026-07-14 22:27:13,707 examples.otherfile INFO      tqdm[Processing items] done: 2/2 (100.0%), elapsed 0.1s, 32.28 it/s, ETA 0.0s
2026-07-14 22:27:13,708 root ERROR     Uncaught exception
2026-07-14 22:27:13,708 root ERROR     Traceback (most recent call last):
2026-07-14 22:27:13,708 root ERROR       File "/home/npu-tao/micromamba/envs/multihop/lib/python3.10/runpy.py", line 196, in _run_module_as_main
2026-07-14 22:27:13,708 root ERROR         return _run_code(code, main_globals, None,
2026-07-14 22:27:13,708 root ERROR       File "/home/npu-tao/micromamba/envs/multihop/lib/python3.10/runpy.py", line 86, in _run_code
2026-07-14 22:27:13,708 root ERROR         exec(code, run_globals)
2026-07-14 22:27:13,708 root ERROR       File "/media/npu-tao/disk4T/jason/logging-tee/examples/demo.py", line 77, in <module>
2026-07-14 22:27:13,708 root ERROR         cause_exception()
2026-07-14 22:27:13,708 root ERROR       File "/media/npu-tao/disk4T/jason/logging-tee/examples/otherfile.py", line 13, in cause_exception
2026-07-14 22:27:13,708 root ERROR         raise ValueError("This is an error message\nwith multiple lines\nand should be logged properly.")
2026-07-14 22:27:13,708 root ERROR     ValueError: This is an error message
2026-07-14 22:27:13,708 root ERROR     with multiple lines
2026-07-14 22:27:13,708 root ERROR     and should be logged properly.
```

# Contributing

Increase `version` in [pyproject.toml](pyproject.toml) file.

Modify the `src` folder.

If using `logging_tee` in other repository

```bash
export PYTHONPATH=<path-to-folder>/src:$PYTHONPATH
python -c "import logging_tee; print(logging_tee)"
```

If using `logging_tee` in this repository

```bash
export PYTHONPATH=src/:$PYTHONPATH
python -c "import logging_tee; print(logging_tee)"
```

Run the test

```
python -m pytest tests -s
```

Build the package

```bash
python -m pip install build
python -m build
pip install dist/*.whl
python -c "import logging_tee; print(logging_tee)"
```

Upload to TestPyPI first

```bash
python -m pip install twine
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple logging-tee
```

Upload to PyPi

```bash
python -m twine upload dist/*
```