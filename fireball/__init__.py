import functools
import importlib
import importlib.util
import inspect
import logging
import os
import pdb
import bdb
import sys
import shlex
import traceback
from collections import namedtuple

import fire
from pyinstrument import Profiler

logger = logging.getLogger(__name__)


def pdb_excepthook(type_, value, traceback_):
    # Quitting pdb should not be caught.
    if type_ is bdb.BdbQuit:
        return

    logger.error(''.join(traceback.format_exception(type_, value, traceback_)))
    pdb.pm()


def take_over_excepthook(excepthook):
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


def meta_print_template(arguments_copy, break_limit=79, indent=4):
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


def show_params(arguments_copy):
    meta_print_template(arguments_copy)


def print_template_multiline(arguments_copy):
    meta_print_template(arguments_copy, break_limit=0)


def mock_arguments(func):
    sig = inspect.signature(func)

    mock_arguments_copy = {}
    for param in sig.parameters.values():

        value = param.default
        if value is inspect.Parameter.empty:
            value = '<required>'

        mock_arguments_copy[param.name] = value

    return mock_arguments_copy


def print_template(func, break_limit=None):
    mock_arguments_copy = mock_arguments(func)
    if break_limit is None:
        meta_print_template(mock_arguments_copy)
    else:
        meta_print_template(mock_arguments_copy, break_limit=0)


def print_template_multiline_doc_from_arguments(arguments_copy):
    lines = ['multiline doc parameters:', '']

    lines.append('fireball "$(cat << EOF')
    lines.append('')

    lines.append('# Entrypoint')
    entrypoint = ':'.join(sys.argv[0].strip().split(':')[:2])
    lines.append(entrypoint)
    lines.append('')

    lines.append('# Arguments')
    for key, val in arguments_copy.items():
        if isinstance(val, bool):
            if val:
                lines.append(f'--{key}')
        else:
            lines.append(f'--{key}="{val}"')

    lines.append('')
    lines.append('EOF')
    lines.append(')"')

    logger.info('\n'.join(lines))


def print_template_multiline_doc(func):
    mock_arguments_copy = mock_arguments(func)
    print_template_multiline_doc_from_arguments(mock_arguments_copy)


def wrap_func(
    func,
    print_template,
    template_format_multiline_doc,
    template_format_multiline,
    hook_debugger,
    hook_profiler,
):
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        arguments_copy = bound_args.arguments.copy()

        if print_template:
            if template_format_multiline_doc:
                print_template_multiline_doc(arguments_copy)
            elif template_format_multiline:
                print_template_multiline(arguments_copy)
            else:
                show_params(arguments_copy)

        if hook_debugger:
            take_over_excepthook(pdb_excepthook)

        profiler = None
        if hook_profiler:
            profiler = Profiler()
            profiler.start()

        out = func(*bound_args.args, **bound_args.kwargs)

        if hook_profiler:
            profiler.stop()
            logger.info('profiler.print():')
            profiler.print(show_all=True)

        return out

    return wrapper


ModeDesc = namedtuple('Mode', ['name', 'name_abbr', 'type', 'msg'])

mode_descs = [
    ModeDesc('print-template', 'pt', bool, 'print the template.'),
    ModeDesc('print-only-template', 'pot', bool, 'print only the template then abort.'),
    ModeDesc('template-format', 'tfm', str, 'force to multiline/multiline-doc format.'),
    ModeDesc('hook-debugger', 'hd', bool, 'hook debugger (pdb).'),
    ModeDesc('hook-profiler', 'hp', bool, 'hook profiler (pyinstrument).'),
]
mode_name_to_desc = {mode_desc.name: mode_desc for mode_desc in mode_descs}
mode_name_abbr_to_desc = {mode_desc.name_abbr: mode_desc for mode_desc in mode_descs}


def parse_modes_text(modes_text):
    mode_to_val = {}

    # Extarct.
    components = ()
    if modes_text:
        components = modes_text.split(',')

    for component in components:
        component = component.strip()
        if '=' in component:
            try:
                mode, val = component.split('=')
            except Exception:
                raise RuntimeError(f'Fail to split component={component} into mode and value.')
        else:
            mode = component
            val = None

        if mode in mode_name_to_desc:
            mode_desc = mode_name_to_desc[mode]
        elif mode in mode_name_abbr_to_desc:
            mode_desc = mode_name_abbr_to_desc[mode]
        else:
            raise RuntimeError(f'Invalid mode={mode}')

        if mode_desc.type is not bool:
            if val is None:
                raise RuntimeError(f'Missing value for mode={mode}')
            try:
                val = mode_desc.type(val)
            except Exception:
                raise RuntimeError(
                    f'Failed to convert val={val} to {mode_desc.type} '
                    f'as instructed in mode_desc={mode_desc}.'
                )
        else:
            if val:
                val = bool(val)
            else:
                val = True

        mode_to_val[mode_desc.name] = val

    # Fill the missing modes.
    for mode_desc in mode_descs:
        if mode_desc.name not in mode_to_val:
            mode_to_val[mode_desc.name] = mode_desc.type()

    return mode_to_val


def cli(func, modes_text):
    mode_to_val = parse_modes_text(modes_text)

    template_format = mode_to_val['template-format']
    template_format_multiline = False
    template_format_multiline_doc = False
    if template_format == 'multiline':
        template_format_multiline = True
    elif template_format == 'multiline-doc':
        template_format_multiline_doc = True
    elif template_format:
        raise RuntimeError(f'Invalid template_format={template_format}')

    func = wrap_func(
        func=func,
        print_template=mode_to_val['print-template'],
        template_format_multiline_doc=template_format_multiline_doc,
        template_format_multiline=template_format_multiline,
        hook_debugger=mode_to_val['hook-debugger'],
        hook_profiler=mode_to_val['hook-profiler'],
    )

    if mode_to_val['print-only-template']:
        if template_format_multiline_doc:
            return lambda: print_template_multiline_doc(func)
        elif template_format_multiline:
            return lambda: print_template(func, break_limit=0)
        else:
            return lambda: print_template(func)

    return lambda: fire.Fire(func)


def exec_argv(argv):
    # Input:
    # fireball <module_path>:<func_name>[:...] ...
    # |        |                               ^ argv[2:]
    # |        ^ argv[1]
    # ^ argv[0]
    modes_msg = []
    for mode_desc in mode_descs:
        modes_msg.append(f'- {mode_desc.name}, {mode_desc.name_abbr}: {mode_desc.msg}')
    modes_msg = '\n'.join(modes_msg)

    help_msg = f'''
# Default style

fireball <module_path>:<func_name>[:<modes>] ...

Supported <modes> (comma-seperated):

{modes_msg}

Example:

fireball os:getcwd
fireball base64:b64encode:pot
fireball base64:b64encode:pot,tfm=multiline
fireball foo/bar.py:baz


# Multiline doc style

fireball - << EOF
<module_path>:<func_name>[:<modes>]
...
EOF

Example:

fireball "$(cat << EOF

# Entrypoint
base64:b64encode

# Arguments
--s="<required>"
--altchars="None"

EOF
)"
'''
    if len(argv) < 2:
        logger.error(help_msg)
        sys.exit(1)

    func_path = argv[1]

    if ':' not in func_path:
        logger.error('<func_path>: should have format like "foo.bar:baz".')
        sys.exit(1)

    components = func_path.strip().split(':')
    if len(components) == 2:
        module_path, func_name = components
        modes_text = None
    elif len(components) == 3:
        module_path, func_name, modes_text = components
    else:
        logger.error(f'components={components}')
        logger.error(help_msg)
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
    sys.argv = argv[1:]

    # Call function.
    func_cli = cli(func, modes_text)
    func_cli()


def parse_multiline_doc(multiline_doc):
    argv = ['fireball']
    argv.extend(shlex.split(multiline_doc, comments=True))
    return argv


def exec():
    logging.basicConfig(
        format=os.getenv('LOGGING_FORMAT', '%(message)s'),
        level=os.getenv('LOGGING_LEVEL', 'INFO'),
    )

    argv = sys.argv

    if len(argv) == 2 and '\n' in argv[1]:
        # multiline_doc style.
        argv = parse_multiline_doc(argv[1])

    exec_argv(argv)
