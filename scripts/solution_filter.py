#!/usr/bin/env python3
# coding: utf8

import argparse
import json
import os
import pathlib
import re
import sys
from wcmatch import glob

parser = argparse.ArgumentParser(description='Generates a Visual Studio solution filter file based on specified glob patterns.')

parser.add_argument('--pattern', type=str,
                    help='A list of glob patterns used for matching the projects. Use \'!\' to negate.', required=True)
parser.add_argument('--output', type=str,
                    help='The destination solution filter filename.')
parser.add_argument('--check', action='store_true',
                    help='Checks for each matching project whether the project file exists')
parser.add_argument('solution', type=str, nargs='?',
                    help='The source solution filename.')

args = parser.parse_args()

if args.solution is None or args.solution == '':
    solutions = glob.glob('*.sln')
    if len(solutions) == 0:
        print("No Visual Studio solution file found in the current directory")
        sys.exit(1)
    if len(solutions) > 1:
        print("Please manually specify the Visual Studio solution file to use, as multiple solutions are present in the current directory")
        sys.exit(1)
    args.solution = solutions[0]

if not args.solution.endswith('.sln'):
    print('Unsupported file-extension for Visual Studio solution file')
    sys.exit(1)

if args.output is not None and not args.output.endswith('.slnf'):
    print('Unsupported file-extension for Visual Studio solution filter file')
    sys.exit(1)

args.solution = os.path.normpath(args.solution)
print(f'Using solution \'{args.solution}\' ...')

output = str(pathlib.Path(args.solution).with_suffix('.Filtered.slnf')) if args.output is None else args.output
output = os.path.normpath(output)
patterns = list(map(str.strip, args.pattern.strip('\'').replace(';', '\n').splitlines()))
excluded = list(map(lambda x: x[1:], filter(lambda x: x.startswith('!'), patterns)))
patterns = list(filter(lambda x: not x.startswith('!'), patterns))
patterns = ['**'] if len(patterns) == 0 else patterns


def windows_path(path: str):
    # Replace '/' with '\' on Windows platform
    path = path if os.altsep is None else path.replace(os.altsep, os.sep)
    return os.path.normpath(path)


reguid = r'[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
regex = re.compile(
    r'Project\("\{(?P<type>' + reguid + r')\}"\) = "(?P<name>.+?)", "(?P<filename>.+?)", "\{(?P<id>' + reguid + r')\}"',
    flags=re.IGNORECASE
)

PROJECT_FOLDERS = '66A26720-8FB5-11D2-AA7E-00C04F688DDE'.casefold()
SOLUTION_FOLDER = '2150E333-8FDC-42A3-9474-1A3956D46DE8'.casefold()

projects = set()

with open(args.solution, 'r') as file:
    for line in file:
        match = regex.search(line.rstrip().lstrip())
        if not match:
            continue

        t = match.group('type')
        if t.casefold() in {PROJECT_FOLDERS, SOLUTION_FOLDER}:
            continue

        f = match.group('filename')
        w = windows_path(f)

        if glob.globmatch(w, patterns=patterns, exclude=excluded, flags=glob.FORCEWIN | glob.GLOBSTAR):
            print(f'Found matching project \'{f}\'')
            projects.add(f)

# Solution must be relative to the output directory
solution = os.path.abspath(args.solution)
base = os.path.commonpath([os.path.abspath(output), solution])
solution = os.path.relpath(solution, base)

result = {
    "solution": {
        "path": solution,
        "projects": list(projects)
    }
}

with open(output, 'w') as file:
    json.dump(result, file, indent=4)
