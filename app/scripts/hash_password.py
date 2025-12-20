import click
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


@click.command()
@click.argument('password', required=True)
def main(password: str) -> None:
    """Hash a password using bcrypt"""
    if not password:
        click.echo("Error: Password can't be empty", err=True)
        raise click.Abort()

    hashed = password_hash.hash(password)
    click.echo(hashed)


if __name__ == '__main__':
    main()
