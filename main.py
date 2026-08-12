"""Discord Leagueボットのエントリポイント。

環境変数をロードし、ボットを起動します。
"""

import os
from dotenv import load_dotenv
from src.bot import LeagueBot


def main() -> None:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required in environment variables")

    bot = LeagueBot()
    bot.run(token)


if __name__ == "__main__":
    main()
