import functools
import inspect
import sys

print('ps1', hasattr(sys, 'ps1'))


def foo(a, b, c=1):
    pass


@functools.wraps(foo)
def bar(*arg, **kwargs):
    pass


@functools.wraps(foo)
def baz(*arg, pdb=False, **kwargs):
    pass


print(functools.WRAPPER_UPDATES)


print(inspect.signature(foo))
print(inspect.signature(bar))

# PATCH BAZ.
sig = inspect.signature(baz)
assert 'pdb' not in sig.parameters
print(sig.parameters['c'].kind)
print(sig.parameters['c'].empty)
print(sig.parameters['c'].default)
parameters = list(sig.parameters.values())
parameters.append(inspect.Parameter(name='pdb', default=False, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD))

new_sig = sig.replace(parameters=parameters)
baz.__signature__ = new_sig

print(inspect.signature(baz))

import fire

fire.Fire(baz)
