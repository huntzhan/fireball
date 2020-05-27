import functools
import inspect
import sys
import traceback
import pdb

import fire


def pdb_excepthook(type_, value, traceback_):
    traceback.print_exception(type_, value, traceback_)
    pdb.pm()


def take_over_excepthook(option, excepthook):
    good = True

    if hasattr(sys, 'ps1'):
        sys.stderr.write(
            f'[fireball] {option}: Cannot take-over sys.excepthook '
            'since we are in iterative mode.\n'
        )
        good = False

    if not sys.stderr.isatty():
        sys.stderr.write(
            f'[fireball] {option}: Cannot take-over sys.excepthook '
            'since we don\'t have a tty-like device.\n'
        )
        good = False

    if good:
        sys.stdout.write(f'[fireball] {option}: Setup successfully.\n')
        sys.excepthook = excepthook


def cli(func):
    sig_func = inspect.signature(func)

    PARAM_PDB_ON_ERROR = 'pdb_on_error'
    func_contains_param_pdb_on_error = PARAM_PDB_ON_ERROR in sig_func.parameters

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = wrapper.__signature__.bind(*args, **kwargs)

        # Pop injected parameters.
        pdb_on_error = False
        if not func_contains_param_pdb_on_error:
            pdb_on_error = bound_args.arguments.pop(PARAM_PDB_ON_ERROR)

        # PDB.
        if pdb_on_error:
            take_over_excepthook(PARAM_PDB_ON_ERROR, pdb_excepthook)

        return func(**bound_args.arguments)

    # Patch signature.
    sig_wrapper = inspect.signature(wrapper)
    new_parameters = list(sig_wrapper.parameters.values())

    if not func_contains_param_pdb_on_error:
        new_parameters.append(
            inspect.Parameter(
                name=PARAM_PDB_ON_ERROR,
                default=False,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        )

    new_sig_wrapper = sig_wrapper.replace(parameters=new_parameters)
    wrapper.__signature__ = new_sig_wrapper

    # Bind to python-fire.
    return lambda: fire.Fire(wrapper)
