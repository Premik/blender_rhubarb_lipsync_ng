from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Iterator

from github import Github
from github.GitRelease import GitRelease
from github.Repository import Repository


@dataclass
class GithubReleaseManager:
    repo_name: str = "Premik/blender_rhubarb_lipsync_ng"

    @cached_property
    def github(self) -> Github:
        token_path = Path.home() / "github-token.txt"
        token = token_path.read_text().strip()
        return Github(token)

    @cached_property
    def repo(self) -> Repository:
        return self.github.get_repo(self.repo_name)

    def list_releases(self) -> Iterator[GitRelease]:
        for release in self.repo.get_releases():
            yield release

    def save_release_history(self, output_file: str) -> None:
        """Save release history to a markdown file."""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Release History\n\n")

            for release in self.list_releases():
                title = release.title or release.tag_name
                f.write(f"## {title}\n\n")

                # Write date
                release_date = release.created_at.strftime("%Y-%m-%d")
                f.write(f"**Date:** {release_date}\n\n")

                if release.body:
                    f.write(release.body)
                    f.write("\n\n")

                # Add separator between releases
                f.write("---\n\n")


def main() -> None:
    manager = GithubReleaseManager()
    output_file = "release_notes.md"
    manager.save_release_history(output_file)
    print(f"Release history saved to {output_file}")


if __name__ == "__main__":
    main()
