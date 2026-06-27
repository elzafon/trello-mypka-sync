import os


def write_card(target_path, frontmatter, body):
    """Write a PKA markdown file, creating parent dirs as needed."""
    os.makedirs(os.path.dirname(target_path), mode=0o777, exist_ok=True)
    content = frontmatter + "\n"
    if body:
        content += "\n" + body + "\n"
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(target_path, 0o666)
    return target_path
