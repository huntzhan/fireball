import fireball


def should_raise(a, b=1):
    if b == 42:
        raise ValueError()


should_raise_cli = fireball.cli(should_raise)
should_raise_cli()
