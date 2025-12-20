import bcrypt
import click


@click.command()
@click.argument('password', required=True)
def main(password: str) -> None:
    """Hash a password using bcrypt"""
    if not password:
        click.echo("Error: Password can't be empty", err=True)
        raise click.Abort()

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    click.echo(hashed)


if __name__ == '__main__':
    main()
