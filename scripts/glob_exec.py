#!/usr/bin/env python3
# coding: utf8

import argparse
import asyncio
import locale
import os
import subprocess
import sys
from timeit import default_timer as timer
from wcmatch import glob

parser = argparse.ArgumentParser(description='Executes a specified command for each matching file.')

parser.add_argument('--pattern', type=str,
                    help='A list of glob patterns used for matching the files. Use \'!\' to negate.', required=True)
parser.add_argument('--maxdop', type=int, default=1,
                    help='The maximum degree of parallelism. Pass \'0\' to use the number of logical CPU cores.')
parser.add_argument('--fail-fast', action='store_true',
                    help='Immediately stop processing of subsequent files if a previous execution failed.')
parser.add_argument('--ignore-errors', action='store_true',
                    help='Ignore all execution errors and always return a success status code.')
parser.add_argument('args', nargs=argparse.REMAINDER,
                    help='The command to be executed for each matching file.')

args = parser.parse_args()

if len(args.args) == 0:
    print('Please specify a command to execute for each matching file')
    sys.exit(1)

if '{}' not in args.args:
    print('The provided command must contain at least one occurrence of the placeholder \'{}\'')
    sys.exit(1)

maxdop = os.cpu_count() if args.maxdop == 0 else args.maxdop
print(f'Degree of parallelism: {maxdop}')

encoding = os.device_encoding(0)
encoding = locale.getpreferredencoding(False) if encoding is None else encoding

command = list(map(lambda x: x.replace('\\{\\}', '{}'), args.args))
patterns = list(map(str.strip, args.pattern.strip('\'').replace(';', '\n').splitlines()))
excluded = list(map(lambda x: x[1:], filter(lambda x: x.startswith('!'), patterns)))
patterns = list(filter(lambda x: not x.startswith('!'), patterns))

if len(patterns) == 0:
    print('Please specify at least one \'inclusive\' glob pattern')
    sys.exit(1)


class ExecutionFailed(BaseException):
    def __init__(self, returncode):
        self.returncode = returncode
        super().__init__("Execution failed")


async def execute(id, file, command, *command_args):
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            command, *command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True
        )

        print(f'{id:02d}: Processing file \'{file}\' ...', flush=True)
        while True:
            line = await proc.stdout.readline()
            if line:
                output = line.strip().decode(encoding, errors='replace')
                print(f'{id:02d}: {output}', flush=True)
            else:
                break

        await proc.wait()

        if args.fail_fast and proc.returncode != 0:
            raise ExecutionFailed(proc.returncode)

        return proc.returncode

    except asyncio.CancelledError:
        if proc is not None and proc.returncode is None:
            proc.terminate()
            proc._transport.close()  # https://bugs.python.org/issue43884
        raise


async def execute_with_maxdop(semaphore, id, file, command, *command_args):
    async with semaphore:
        return await execute(id, file, command, *command_args)


async def gather(*tasks, **kwargs):
    tasks = [
        task if isinstance(task, asyncio.Task) else asyncio.create_task(task)
        for task in tasks
    ]
    try:
        return await asyncio.gather(*tasks, **kwargs)
    except ExecutionFailed as e:
        for task in tasks:
            task.cancel()
        return [e.returncode]


async def main():
    semaphore = asyncio.Semaphore(maxdop)
    start = timer()

    tasks = [
        execute_with_maxdop(
            semaphore,
            id, file, command[0], *map(lambda x: x.replace('{}', f'{file}'), command[1:]))
        for id, file in enumerate(glob.iglob(patterns=patterns, exclude=excluded, flags=glob.GLOBSTAR))
    ]

    result = await gather(*tasks)

    elapsed = timer() - start
    print(f'Processing completed after \'{elapsed}\' seconds.') 

    if not args.ignore_errors:
        if len(result) == 1:
            sys.exit(result[0])

        if any(x != 0 for x in result):
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
