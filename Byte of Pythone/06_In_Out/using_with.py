#! /usr/bin/env python3

with open("poem.txt") as f:
    for line in f:
        print(line, end='')