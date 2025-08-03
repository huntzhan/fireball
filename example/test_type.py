'''
fib example/test_type.py:example0:pot
fib example/test_type.py:example0 --a="42" --b="42" --c="['1','2','3']"
'''

import typer
from typing import List


def example0(
        a: int = typer.Option(),
        b: str = typer.Option(),
        c: List[str] = typer.Option(),
        d: bool = typer.Option(default=False),
):
    print('a', type(a), a)
    print('b', type(b), b)
    print('c', type(c), c)
    print('d', type(d), d)


def example1(
    a: int,
    b: list[str],
    c: str = '42',
    d: bool = False,
):
    print('a', type(a), a)
    print('b', type(b), b)
    print('c', type(c), c)
    print('d', type(d), d)
