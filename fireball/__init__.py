import functools
import importlib
import inspect
import logging
import os
import pdb
import bdb
import sys
import shlex
import traceback
from signal import signal, SIGPIPE, SIG_DFL
from collections import namedtuple

import fire
from pyinstrument import Profiler

logger = logging.getLogger(__name__)


class ExecName:
    exec_name = None


def pdb_excepthook(type_, value, traceback_):
    # Quitting pdb should not be caught.
    if type_ is bdb.BdbQuit:
        return

    logger.error(''.join(traceback.format_exception(type_, value, traceback_)))
    pdb.pm()


def takeover_excepthook(excepthook):
    good = True

    if hasattr(sys, 'ps1'):
        logger.warning('Cannot take-over sys.excepthook ' 'since we are in iterative mode.',)
        good = False

    if not sys.stderr.isatty():
        logger.warning(
            'Cannot take-over sys.excepthook '
            'since we don\'t have a tty-like device.',
        )
        good = False

    if good:
        logger.debug('PDB Hooked.')
        sys.excepthook = excepthook


def print_template(arguments, break_limit=79, indent=4):
    entrypoint = ':'.join(sys.argv[0].strip().split(':')[:2])
    components = [ExecName.exec_name, entrypoint]
    for key, val in arguments.items():
        if isinstance(val, bool):
            if val:
                components.append(f'--{key}')
        else:
            components.append(f'--{key}="{val}"')

    one_line = ' '.join(components)
    if len(one_line) <= break_limit:
        sys.stdout.write(one_line + '\n')

    else:
        lines = [components[0] + ' ' + components[1] + ' \\']
        for idx, component in enumerate(components[2:], start=2):
            prefix = ' ' * indent
            suffix = ' \\' if idx < len(components) - 1 else ''
            lines.append(prefix + component + suffix)
        sys.stdout.write('\n'.join(lines) + '\n')


def print_template_multiline(arguments):
    print_template(arguments, break_limit=0)


def print_template_multiline_doc(arguments):
    lines = []

    lines.append(f'{ExecName.exec_name} "$(cat << EOF')
    lines.append('')

    lines.append('# Entrypoint')
    entrypoint = ':'.join(sys.argv[0].strip().split(':')[:2])
    lines.append(entrypoint)
    lines.append('')

    lines.append('# Arguments')
    for key, val in arguments.items():
        if isinstance(val, bool):
            if val:
                lines.append(f'--{key}')
        else:
            lines.append(f'--{key}="{val}"')

    lines.append('')
    lines.append('EOF')
    lines.append(')"')

    logger.info('\n'.join(lines))


def extract_arguments(func):
    sig = inspect.signature(func)

    mock_arguments = {}
    for param in sig.parameters.values():

        value = param.default
        if value is inspect.Parameter.empty:
            value = 'REQUIRED'

        mock_arguments[param.name] = value

    return mock_arguments


def wrap_func(
    func,
    flag_print_template,
    flag_template_format_multiline_doc,
    flag_template_format_multiline,
    flag_hook_debugger,
    flag_hook_profiler,
):
    sig = inspect.signature(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()

        arguments = bound_args.arguments.copy()

        if flag_print_template:
            if flag_template_format_multiline_doc:
                print_template_multiline_doc(arguments)
            elif flag_template_format_multiline:
                print_template_multiline(arguments)
            else:
                print_template(arguments)

        if flag_hook_debugger:
            takeover_excepthook(pdb_excepthook)

        profiler = None
        if flag_hook_profiler:
            profiler = Profiler()
            profiler.start()

        out = func(*bound_args.args, **bound_args.kwargs)

        if flag_hook_profiler:
            profiler.stop()
            logger.info('profiler.print():')
            profiler.print(show_all=True)

        return out

    return wrapper


ModeDesc = namedtuple('Mode', ['name', 'name_abbr', 'type', 'msg'])

mode_descs = [
    ModeDesc('print-template', 'pt', bool, 'print the template.'),
    ModeDesc('print-only-template', 'pot', bool, 'print only the template then abort.'),
    ModeDesc('template-format', 'tf', str, 'force to multiline/multiline-doc format.'),
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
            # Pattern "key=val".
            try:
                mode, val = component.split('=')
            except Exception:
                logger.error(
                    f'Fail to split component={component} into mode and value.\n'
                    f'modes_text={modes_text}'
                )
                sys.exit(1)
        else:
            # Pattern "a,b,c".
            mode = component
            val = None

        if mode in mode_name_to_desc:
            # Find the name first.
            mode_desc = mode_name_to_desc[mode]
        elif mode in mode_name_abbr_to_desc:
            # Then the name_attr.
            mode_desc = mode_name_abbr_to_desc[mode]
        else:
            logger.error(f'Invalid mode={mode}\nmodes_text={modes_text}')
            sys.exit(1)

        if mode_desc.type is not bool:
            # The only supported for now is str.
            if val is None:
                logger.error(f'Missing value for mode={mode}\nmodes_text={modes_text}')
                sys.exit(1)
            try:
                val = mode_desc.type(val)
            except Exception:
                logger.error(
                    f'Failed to convert val={val} to {mode_desc.type} '
                    f'as instructed in mode_desc={mode_desc}.\n'
                    f'modes_text={modes_text}'
                )
                sys.exit(1)
        else:
            # bool.
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
    flag_template_format_multiline = False
    flag_template_format_multiline_doc = False
    if template_format == 'multiline':
        flag_template_format_multiline = True
    elif template_format == 'multiline-doc':
        flag_template_format_multiline_doc = True
    elif template_format:
        logger.error(f'Invalid template_format={template_format}\nmodes_text={modes_text}')
        sys.exit(1)

    func = wrap_func(
        func=func,
        flag_print_template=mode_to_val['print-template'],
        flag_template_format_multiline_doc=flag_template_format_multiline_doc,
        flag_template_format_multiline=flag_template_format_multiline,
        flag_hook_debugger=mode_to_val['hook-debugger'],
        flag_hook_profiler=mode_to_val['hook-profiler'],
    )

    if mode_to_val['print-only-template']:
        if flag_template_format_multiline_doc:
            return lambda: print_template_multiline_doc(extract_arguments(func))
        elif flag_template_format_multiline:
            return lambda: print_template_multiline(extract_arguments(func))
        else:
            return lambda: print_template(extract_arguments(func))

    return lambda: fire.Fire(func)


def get_exec_name(argv):
    if argv[0].endswith('fib'):
        return 'fib'
    elif argv[0].endswith('fireball'):
        return 'fireball'
    logger.error(f'Invalid argv[0]={argv[0]}')
    sys.exit(1)


def exec_argv(argv):
    # Input:
    # fireball <module_path>:<func_name>[:...] ...
    # |        |                               ^ argv[2:]
    # |        ^ argv[1]
    # ^ argv[0]
    ExecName.exec_name = get_exec_name(argv)

    modes_msg = []
    for mode_desc in mode_descs:
        modes_msg.append(f'- {mode_desc.name}, {mode_desc.name_abbr}: {mode_desc.msg}')
    modes_msg = '\n'.join(modes_msg)

    help_msg = f'''
# Default style

{ExecName.exec_name} <module_path>:<func_name>[:<modes>] ...

Supported <modes> (comma-seperated):

{modes_msg}

Example:

{ExecName.exec_name} os:getcwd
{ExecName.exec_name} base64:b64encode:pot
{ExecName.exec_name} base64:b64encode:pot,tf=multiline
{ExecName.exec_name} foo/bar.py:baz


# Multiline doc style

{ExecName.exec_name} - << EOF
<module_path>:<func_name>[:<modes>]
...
EOF

Example:

{ExecName.exec_name} "$(cat << EOF

# Entrypoint
base64:b64encode

# Arguments
--s="b'{ExecName.exec_name}'"
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
        logger.exception(f'importlib.import_module cannot find or load module {module_path}.')
        sys.exit(1)

    # Load function.
    func = getattr(module, func_name)
    if func is None:
        logger.error(f'Cannot find function {func_name}.')
        sys.exit(1)

    # Patch to <module_path>:<func_name> ...
    sys.argv = argv[1:]

    # Call function.
    func_cli = cli(func, modes_text)
    func_cli()


def parse_multiline_doc(exec_name, multiline_doc):
    argv = [exec_name]
    argv.extend(shlex.split(multiline_doc, comments=True))
    return argv


def exec():
    logging.basicConfig(
        format=os.getenv('LOGGING_FORMAT', '%(message)s'),
        level=os.getenv('LOGGING_LEVEL', 'INFO'),
    )

    # https://stackoverflow.com/questions/14207708/ioerror-errno-32-broken-pipe-when-piping-prog-py-othercmd
    signal(SIGPIPE, SIG_DFL)

    argv = sys.argv

    if len(argv) == 2 and '\n' in argv[1]:
        # multiline_doc style.
        argv = parse_multiline_doc(get_exec_name(argv), argv[1])

    exec_argv(argv)
