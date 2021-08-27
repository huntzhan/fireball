def print_list(data):
    breakpoint()
    print(type(data))
    print(data)


def some_opt():
    for _ in range(10000000):
        pass


def test_profiler():
    import time
    time.sleep(1)
    some_opt()


def test_exp():
    assert 0


def bar():
    import inspect
    caller_frame = inspect.currentframe().f_back
    print(caller_frame.f_globals['__name__'])


def foo():
    bar()


def free_opt(*args, **kwargs):
    print(args)
    print(kwargs)
