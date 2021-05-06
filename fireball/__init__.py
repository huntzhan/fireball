import functools
import importlib
import importlib.util
import inspect
import logging
import os
import pdb
import bdb
import sys
import traceback

import fire

logging.basicConfig(format='%(message)s', level=os.getenv('LOGGING_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)


def pdb_excepthook(type_, value, traceback_):
    # Quitting pdb should not be caught.
    if type_ is bdb.BdbQuit:
        return

    logger.error(''.join(traceback.format_exception(type_, value, traceback_)))
    pdb.pm()


def fireball_take_over_excepthook(excepthook):
    good = True

    if hasattr(sys, 'ps1'):
        logger.warning(
            'mode=d: Cannot take-over sys.excepthook '
            'since we are in iterative mode.',
        )
        good = False

    if not sys.stderr.isatty():
        logger.warning(
            'mode=d: Cannot take-over sys.excepthook '
            'since we don\'t have a tty-like device.',
        )
        good = False

    if good:
        logger.debug('mode=d: PDB Hooked.')
        sys.excepthook = excepthook


def fireball_meta_show_params(arguments_copy, break_limit=79, indent=2):
    entrypoint = ':'.join(sys.argv[0].strip().split(':')[:2])
    components = ['fireball', entrypoint]
    for key, val in arguments_copy.items():
        if isinstance(val, bool):
            if val:
                components.append(f'--{key}')
        else:
            components.append(f'--{key}="{val}"')

    header = 'Parameters:\n'
    one_line = ' '.join(components)
    if len(one_line) <= break_limit:
        logger.info(header + '\n' + one_line + '\n')

    else:
        lines = [components[0] + ' ' + components[1] + ' \\']
        for idx, component in enumerate(components[2:], start=2):
            prefix = ' ' * indent
            suffix = ' \\' if idx < len(components) - 1 else ''
            lines.append(prefix + component + suffix)
        logger.info(header + '\n' + '\n'.join(lines) + '\n')


def fireball_show_params(arguments_copy):
    fireball_meta_show_params(arguments_copy)


def fireball_show_params_mtl(arguments_copy):
    fireball_meta_show_params(arguments_copy, break_limit=0)


def fireball_show_params_tpl(func, break_limit=None):
    sig = inspect.signature(func)

    mock_arguments_copy = {}
    for param in sig.parameters.values():

        value = param.default
        if value is inspect.Parameter.empty:
            value = '<required>'

        mock_arguments_copy[param.name] = value

    if break_limit is None:
        fireball_meta_show_params(mock_arguments_copy)
    else:
        fireball_meta_show_params(mock_arguments_copy, break_limit=0)


def wrap_func(
    func,
    print_template_before_execution,
    force_multi_line,
    hook_pdb,
):
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        arguments_copy = bound_args.arguments.copy()

        if print_template_before_execution:
            if force_multi_line:
                fireball_show_params_mtl(arguments_copy)
            else:
                fireball_show_params(arguments_copy)

        if hook_pdb:
            fireball_take_over_excepthook(pdb_excepthook)

        # python-fire will write this to stdout/stderr.
        return func(*bound_args.args, **bound_args.kwargs)

    return wrapper


def cli(func, modes):
    modes = {char: True for char in modes or ()}

    print_only_template = modes.pop('t', False)
    print_template_before_execution = modes.pop('p', False)
    force_multi_line = modes.pop('m', False)
    hook_pdb = modes.pop('d', False)

    if modes:
        logger.error(f'Invalid modes={list(modes)}')
        sys.exit(1)

    func = wrap_func(
        func,
        print_template_before_execution,
        force_multi_line,
        hook_pdb,
    )

    if print_only_template:
        if force_multi_line:
            return lambda: fireball_show_params_tpl(func, break_limit=0)
        else:
            return lambda: fireball_show_params_tpl(func)

    return lambda: fire.Fire(func)


def exec():
    # Input.
    # fireball <module_path>:<func_name>[:...] ...
    # |        |                               ^ sys.argv[2:]
    # |        ^ sys.argv[1]
    # ^ sys.argv[0]
    error_msg = (
        'fireball <module_path>:<func_name>[:<modes>] ...\n'
        '\n'
        '<modes>:\n'
        '- "t": print only the template then abort.\n'
        '- "p": print the template before execution.\n'
        '- "m": force multi-line format.\n'
        '- "d": hook pdb.\n'
        '\n'
        'Example: fireball os:getcwd\n'
        '         fireball foo/bar.py:baz\n'
    )
    if len(sys.argv) < 2:
        logger.error(error_msg)
        sys.exit(1)

    func_path = sys.argv[1]

    if ':' not in func_path:
        logger.error('<func_path>: should have format like "foo.bar:baz".')
        sys.exit(1)

    components = func_path.strip().split(':')
    if len(components) == 2:
        module_path, func_name = components
        modes = None
    elif len(components) == 3:
        module_path, func_name, modes = components
    else:
        logger.error(f'components={components}')
        logger.error(error_msg)
        sys.exit(1)

    if not module_path:
        logger.error('Missing module_path.')
        sys.exit(1)
    if not func_name:
        logger.error('Missing func_name.')
        sys.exit(1)

    # Support raw path.
    if '/' in module_path:
        module_path = module_path.replace('/', '.')
    if module_path.endswith('.py'):
        module_path = module_path[:-3]

    # Add the current working directory to sys.path for non-package import.
    cwd_path = os.getcwd()
    if cwd_path not in sys.path:
        sys.path.append(cwd_path)

    # Load module.
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.error('importlib.import_module cannot find or load module %s.', module_path)
        logger.error(traceback.format_exc())
        sys.exit(1)

    # Load function.
    func = getattr(module, func_name)
    if func is None:
        logger.error('Cannot find function %s.', func_name)
        sys.exit(1)

    # Patch to <module_path>:<func_name> ...
    sys.argv = sys.argv[1:]

    # Call function.
    func_cli = cli(func, modes)
    func_cli()
