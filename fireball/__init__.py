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


def fireball_take_over_excepthook(option, excepthook):
    good = True

    if hasattr(sys, 'ps1'):
        logger.warning(
            '--%s: Cannot take-over sys.excepthook '
            'since we are in iterative mode.',
            option,
        )
        good = False

    if not sys.stderr.isatty():
        logger.warning(
            '--%s: Cannot take-over sys.excepthook '
            'since we don\'t have a tty-like device.',
            option,
        )
        good = False

    if good:
        logger.debug('--%s: Setup successfully.', option)
        sys.excepthook = excepthook


def fireball_meta_show_params(arguments_copy, break_limit=79, indent=2):
    components = ['fireball', sys.argv[0]]
    for key, val in arguments_copy.items():
        if isinstance(val, bool):
            if val:
                components.append(f'--{key}')
        else:
            components.append(f'--{key}="{val}"')

    header = 'Show parameters:\n'
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


def fireball_inject_param(
    name,
    func_contains_param,
    var_positional_idx,
    var_keyword_idx,
    default,
    parameters,
    injected_params,
):
    if func_contains_param:
        logger.warning('--%s has been defined, skip.', name)
        return

    if var_positional_idx < 0:
        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
    else:
        kind = inspect.Parameter.KEYWORD_ONLY

    if var_keyword_idx < 0:
        insert_idx = len(parameters)
    else:
        insert_idx = var_keyword_idx

    parameters.insert(insert_idx, inspect.Parameter(
        name=name,
        default=default,
        kind=kind,
    ))
    injected_params.add(name)


PARAM_PDB = 'pdb_'
PARAM_SHOW_PARAMS = 'show_params_'
PARAM_SHOW_PARAMS_MTL = 'show_params_mtl_'


def wrap_func(func):
    sig_func = inspect.signature(func)

    func_contains_param_pdb = PARAM_PDB in sig_func.parameters
    func_contains_param_show_params = PARAM_SHOW_PARAMS in sig_func.parameters
    func_contains_param_show_params_mtl = PARAM_SHOW_PARAMS_MTL in sig_func.parameters

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = wrapper.__signature__.bind(*args, **kwargs)
        bound_args.apply_defaults()

        arguments_copy = bound_args.arguments.copy()

        # PDB.
        if not func_contains_param_pdb:
            if bound_args.arguments.pop(PARAM_PDB):
                fireball_take_over_excepthook(PARAM_PDB, pdb_excepthook)

        # Show parameters.
        if not func_contains_param_show_params:
            if bound_args.arguments.pop(PARAM_SHOW_PARAMS):
                fireball_show_params(arguments_copy)

        # Show parameters (force multi-line).
        if not func_contains_param_show_params_mtl:
            if bound_args.arguments.pop(PARAM_SHOW_PARAMS_MTL):
                fireball_show_params_mtl(arguments_copy)

        # python-fire will write this to stdout/stderr.
        return func(*bound_args.args, **bound_args.kwargs)

    # Patch signature.
    sig_wrapper = inspect.signature(wrapper)
    parameters = list(sig_wrapper.parameters.values())

    var_positional_idx = -1
    var_keyword_idx = -1
    for param_idx, param in enumerate(parameters):
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            assert var_positional_idx == -1
            var_positional_idx = param_idx
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            assert var_keyword_idx == -1
            var_keyword_idx = param_idx

    injected_params = set()

    # PDB.
    fireball_inject_param(
        PARAM_PDB,
        func_contains_param_pdb,
        var_positional_idx,
        var_keyword_idx,
        False,
        parameters,
        injected_params,
    )
    # Show parameters.
    fireball_inject_param(
        PARAM_SHOW_PARAMS,
        func_contains_param_show_params,
        var_positional_idx,
        var_keyword_idx,
        False,
        parameters,
        injected_params,
    )
    # Show parameters (force multi-line).
    fireball_inject_param(
        PARAM_SHOW_PARAMS_MTL,
        func_contains_param_show_params_mtl,
        var_positional_idx,
        var_keyword_idx,
        False,
        parameters,
        injected_params,
    )

    new_sig_wrapper = sig_wrapper.replace(parameters=parameters)
    wrapper.__signature__ = new_sig_wrapper

    wrapper.__injected_params__ = injected_params

    return wrapper


PARAM_SHOW_PARAMS_TPL = 'show_params_tpl_'
PARAM_SHOW_PARAMS_TPL_MTL = 'show_params_tpl_mtl_'


def fireball_show_params_tpl(func, break_limit=None):
    sig = func.__signature__
    injected_params = func.__injected_params__

    mock_arguments_copy = {}
    for param in sig.parameters.values():
        if param.name in injected_params:
            continue

        value = param.default
        if value is inspect.Parameter.empty:
            value = '<required>'

        mock_arguments_copy[param.name] = value

    if break_limit is None:
        fireball_meta_show_params(mock_arguments_copy)
    else:
        fireball_meta_show_params(mock_arguments_copy, break_limit=0)


def cli(func):
    func = wrap_func(func)

    # Show the template of parameters.
    if f'--{PARAM_SHOW_PARAMS_TPL}' in sys.argv:
        return lambda: fireball_show_params_tpl(func)
    if f'--{PARAM_SHOW_PARAMS_TPL_MTL}' in sys.argv:
        return lambda: fireball_show_params_tpl(func, break_limit=0)

    return lambda: fire.Fire(func)


def exec():
    # Input.
    # fireball <module_path>:<func_name> ...
    #                                    ^ sys.argv[2:]
    #          ^ sys.argv[1]
    # ^ sys.argv[0]
    if len(sys.argv) < 2:
        logger.error(
            'fireball <module_path>:<func_name>\n'
            'Example: fireball os:getcwd\n'
            '         fireball foo/bar.py:baz'
        )
        sys.exit(1)

    func_path = sys.argv[1]

    if ':' not in func_path:
        logger.error('<func_path>: should have format like "foo.bar:baz".')
        sys.exit(1)

    module_path, func_name = func_path.strip().split(':')
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
    func_cli = cli(func)
    func_cli()
