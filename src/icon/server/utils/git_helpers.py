import logging
import subprocess

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    pass


def convert_https_git_url_to_ssh(https_url: str) -> str:
    """
    Convert a Git repository URL from HTTPS to SSH format.

    Args:
        https_url (str): The HTTPS URL of the Git repository.

    Returns:
        str: The SSH URL of the Git repository.
    """

    if https_url.startswith("git@"):
        return https_url

    if not https_url.startswith("https://"):
        raise ValueError("URL does not start with 'https://'")

    # Remove the 'https://' part
    stripped_url = https_url[8:]

    # Replace the first '/' with ':'
    ssh_url = stripped_url.replace("/", ":", 1)

    return f"git@{ssh_url}"


def convert_ssh_git_url_to_https(ssh_url: str) -> str:
    """
    Convert a Git repository URL from SSH to HTTPS format.

    Args:
        ssh_url (str): The SSH URL of the Git repository.

    Returns:
        str: The HTTPS URL of the Git repository.
    """

    if ssh_url.startswith("https://"):
        return ssh_url

    if not ssh_url.startswith("git@"):
        raise ValueError("URL does not start with 'git@'")

    # Remove the 'git@' part and replace the first ':' with '/'
    stripped_url = ssh_url[4:].replace(":", "/", 1)

    return f"https://{stripped_url}"


def git_fetch_all(cwd: str) -> None:
    try:
        subprocess.run(
            ["git", "fetch", "--all"],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        logger.info("Fetched updates for '%s'", cwd)
    except subprocess.CalledProcessError:
        raise RepositoryError(f"Failed to fetch updates for {cwd!r}.")


def git_clone(repository: str, dir: str) -> None:
    try:
        subprocess.run(
            ["git", "clone", repository, dir],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        logger.info("Repository '%s' successfully cloned to '%s'.", repository, dir)
    except subprocess.CalledProcessError as e:
        raise RepositoryError(f"Failed to clone repository {e}", e)


def git_checkout(git_hash: str, cwd: str) -> None:
    try:
        subprocess.run(
            ["git", "checkout", git_hash],
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        logger.info("Checked out commit '%s' in '%s'", git_hash, cwd)
    except subprocess.CalledProcessError:
        raise RepositoryError(f"Failed to check out commit {git_hash!r}.")


def git_get_remote_url(repository_dir: str) -> str:
    try:
        # Execute the git command and capture its output
        completed_process = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repository_dir,
            stdout=subprocess.PIPE,
            text=True,  # Ensures that stdout will be a string
            check=True,
        )
        return completed_process.stdout.strip()
    except subprocess.CalledProcessError:
        raise RepositoryError(f"{repository_dir!r} does not contain a git repo.")


def checkout_commit(git_hash: str | None, cwd: str) -> None:
    if git_hash is None:
        return

    # First attempt to checkout the commit
    try:
        git_checkout(cwd=cwd, git_hash=git_hash)
    except RepositoryError:
        # If the first attempt fails, fetch updates and try again
        git_fetch_all(cwd=cwd)
        git_checkout(cwd=cwd, git_hash=git_hash)


def local_repo_exists(repository_dir: str, repository: str) -> bool:
    https_url = convert_ssh_git_url_to_https(repository)
    ssh_url = convert_https_git_url_to_ssh(repository)

    try:
        remote_url = git_get_remote_url(repository_dir)
    except RepositoryError:
        return False

    logger.info("'%s' contains repo with remote url '%s'.", repository_dir, remote_url)

    if remote_url not in [https_url, ssh_url]:
        raise RepositoryError(
            f"{repository_dir!r} contains repo different to {repository!r}."
        )

    return True
