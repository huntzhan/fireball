import fireball


def should_raise(a, b=1):
    if b == 42:
        raise ValueError()


def bp_behavior():
    breakpoint()


# should_raise_cli = fireball.cli(should_raise, debug=True)
# should_raise_cli()
