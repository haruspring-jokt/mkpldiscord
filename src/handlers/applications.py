import os

import discord
from discord import ui


def get_apply_forum_ids() -> set[int]:
    """申請フォーラムのチャンネル ID 一覧を返します。"""
    ids: set[int] = set()
    for env_key in ("DISCORD_APPLY_FORUM_ID_DIV1", "DISCORD_APPLY_FORUM_ID_DIV2"):
        raw = os.getenv(env_key, "").strip()
        if not raw:
            continue
        for part in raw.split(","):
            value = part.strip()
            if value and value.isdigit():
                ids.add(int(value))
    return ids


def get_apply_type_options() -> list[tuple[str, str]]:
    """申請種別の一覧を返します。"""
    return [
        ("1", "選手の新規登録"),
        ("2", "選手の登録内容変更"),
        ("3", "選手の登録解除"),
        ("4", "完全移籍の申請"),
        ("5", "レンタル移籍の申請"),
        ("6", "クラブ登録内容の変更"),
        ("7", "その他の申請"),
    ]


def get_apply_type_title(apply_type: str) -> str:
    """モーダルタイトルを返します。"""
    return f"{apply_type}の申請"


def get_apply_type_fields(apply_type: str) -> list[dict[str, object]]:
    """申請種別ごとの入力項目を JSON 形式で返します。"""
    field_map = {
        "選手の新規登録": [
            {
                "label": "選手名",
                "placeholder": "アレックス・カブレラ",
                "required": True,
            },
            {"label": "都道府県", "placeholder": "東京都", "required": True},
            {
                "label": "その他の内容（実績、得意分野、他チーム所属など）",
                "placeholder": "",
                "required": False,
            },
            {"label": "その他備考", "placeholder": "", "required": False},
        ],
        "選手の登録内容変更": [
            {
                "label": "選手名",
                "placeholder": "アレックス・カブレラ",
                "required": True,
            },
            {
                "label": "変更内容",
                "placeholder": "登録名を〇〇→△△に変更",
                "required": True,
            },
            {"label": "その他備考", "placeholder": "", "required": False},
        ],
        "選手の登録解除": [
            {
                "label": "選手名",
                "placeholder": "アレックス・カブレラ",
                "required": True,
            },
            {"label": "その他備考", "placeholder": "", "required": False},
        ],
        "完全移籍の申請": [
            {"label": "現所属クラブ", "placeholder": "ヘルシンキMC", "required": True},
            {
                "label": "選手名",
                "placeholder": "アレックス・カブレラ",
                "required": True,
            },
            {"label": "その他備考", "placeholder": "", "required": False},
        ],
        "レンタル移籍の申請": [
            {"label": "現所属クラブ", "placeholder": "ヘルシンキMC", "required": True},
            {
                "label": "選手名",
                "placeholder": "アレックス・カブレラ",
                "required": True,
            },
            {
                "label": "レンタル期間",
                "placeholder": "2026/10/1～2027/2/28",
                "required": True,
            },
            {
                "label": "レンタル中制約事項",
                "placeholder": "当該クラブ同士の対戦では出場不可",
                "required": True,
            },
            {"label": "その他備考", "placeholder": "", "required": False},
        ],
        "クラブ登録内容の変更": [
            {
                "label": "変更内容",
                "placeholder": "登録名を〇〇→△△に変更",
                "required": True,
            },
            {"label": "その他備考", "placeholder": "", "required": False},
        ],
        "その他の申請": [
            {"label": "その他備考", "placeholder": "", "required": False},
        ],
    }
    return field_map.get(
        apply_type, [{"label": "その他備考", "placeholder": "", "required": False}]
    )


async def handle_thread_create(
    bot: "discord.ext.commands.Bot", thread: discord.Thread
) -> None:
    """申請フォーラムの新規スレッドに対して申請種別の選択を促します。"""
    if not thread.parent_id:
        return
    if thread.parent_id not in get_apply_forum_ids():
        return
    if thread.owner and thread.owner.bot:
        return

    await thread.send(
        "申請の種類を選択してください。\n申請したい内容に該当するボタンを押してください。",
        view=ApplyTypeSelectionView(),
    )


class ApplyTypeSelectionView(ui.View):
    """申請種別選択のためのボタン群。"""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        for code, label in get_apply_type_options():
            self.add_item(ApplyTypeButton(code, label))


class ApplyTypeButton(ui.Button):
    """申請種別を選ぶボタン。"""

    def __init__(self, code: str, label: str) -> None:
        super().__init__(
            custom_id=f"apply_type:{code}",
            label=f"{label}",
            emoji=f"{code}️⃣",
            style=discord.ButtonStyle.secondary,
        )
        self.apply_type = label

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "以下のボタンを押し、申請フォームを開いてください。",
            view=ApplyFormOpenView(self.apply_type),
        )


class ApplyFormOpenView(ui.View):
    """申請フォームを開くためのボタン。"""

    def __init__(self, apply_type: str) -> None:
        super().__init__(timeout=None)
        self.apply_type = apply_type

    @ui.button(label="申請フォームの表示", style=discord.ButtonStyle.primary)
    async def open_modal(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        await interaction.response.send_modal(ApplyRequestModal(self.apply_type))


class ApplyRequestModal(ui.Modal):
    """申請内容の入力用モーダル。"""

    def __init__(self, apply_type: str) -> None:
        super().__init__(title=get_apply_type_title(apply_type))
        self.apply_type = apply_type
        self.inputs: list[ui.TextInput] = []

        for field in get_apply_type_fields(apply_type):
            field_name = str(field["label"])
            placeholder = str(field.get("placeholder", ""))
            required = bool(field.get("required", False))
            is_long = (
                "備考" in field_name
                or "内容" in field_name
                or "制約" in field_name
                or "その他" in field_name
            )
            text_input = ui.TextInput(
                label=field_name,
                style=discord.TextStyle.long if is_long else discord.TextStyle.short,
                required=required,
                placeholder=placeholder,
                max_length=2000,
            )
            self.add_item(text_input)
            self.inputs.append(text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        lines = [f"【{self.title}】"]
        for item in self.inputs:
            value = item.value.strip()
            if value:
                lines.append(f"{item.label}: {value}")

        if not lines[1:]:
            lines.append("入力なし")

        admin_role_id = os.getenv("ADMIN_ROLE_ID", "").strip()
        admin_mention = f"<@&{admin_role_id}>" if admin_role_id else "@運営"
        message = f"{admin_mention}\n" + "\n".join(lines)
        await interaction.channel.send(message)
        await interaction.response.send_message(
            "申請内容をスレッドに送信しました。以降は運営が直接対応します。",
            ephemeral=True,
        )
