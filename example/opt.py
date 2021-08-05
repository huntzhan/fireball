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
