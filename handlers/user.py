from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import LinkPreviewOptions, Message

import database as db
from config import REQUIRED_REFERRALS
from keyboards import channels_keyboard, dashboard_keyboard, status_keyboard, unlock_keyboard
from services import file_service
from services.channel_checker import get_channel_membership_status
from services.referral_service import build_referral_link
from translations import T, get_lang

router = Router()


@router.message(Command("progress"))
async def cmd_progress(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return

    db_user = await db.get_user(user.id)
    if not db_user:
        await message.answer("Please send /start first.")
        return

    all_joined, joined_count, missing = await get_channel_membership_status(bot, user.id)
    if not all_joined:
        await db.update_user(user.id, channels_joined=0)
        if joined_count > 0:
            await message.answer(
                file_service.format_almost_there(missing),
                reply_markup=channels_keyboard(),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        else:
            await message.answer(
                file_service.format_channels_step(),
                reply_markup=channels_keyboard(),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        return

    await db.update_user(user.id, channels_joined=1)
    text = await file_service.format_referral_status(user.id)
    count = db_user.get("referral_count", 0)
    kb = unlock_keyboard() if count >= REQUIRED_REFERRALS else status_keyboard(user.id)
    await message.answer(text, reply_markup=kb)


@router.message(Command("link"))
async def cmd_link(message: Message, bot: Bot) -> None:
    user = message.from_user
    if not user:
        return

    db_user = await db.get_user(user.id)
    if not db_user:
        await message.answer("Please send /start first.")
        return

    all_joined, joined_count, missing = await get_channel_membership_status(bot, user.id)
    if not all_joined:
        await db.update_user(user.id, channels_joined=0)
        if joined_count > 0:
            await message.answer(
                file_service.format_almost_there(missing),
                reply_markup=channels_keyboard(),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        else:
            await message.answer(
                file_service.format_channels_step(),
                reply_markup=channels_keyboard(),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        return

    await db.update_user(user.id, channels_joined=1)
    link = build_referral_link(user.id)
    count = db_user.get("referral_count", 0)
    await message.answer(
        file_service.format_dashboard(user.id, link, count),
        reply_markup=dashboard_keyboard(user.id),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message) -> None:
    user = message.from_user
    if not user:
        return

    db_user = await db.get_user(user.id)
    if not db_user:
        await message.answer("Please send /start first.")
        return

    lang = get_lang(db_user)
    top = await db.get_top_referrers(limit=10)
    rank, my_count = await db.get_user_rank(user.id)

    if not top or all(r.get("referral_count", 0) == 0 for r in top):
        await message.answer(T[lang]["leaderboard_empty"])
        return

    medals = ["🥇", "🥈", "🥉"] + ["  {}".format(i) for i in range(4, 11)]
    lines = [T[lang]["leaderboard_title"], "", T[lang]["leaderboard_prizes"], ""]

    for i, r in enumerate(top):
        count = r.get("referral_count", 0)
        if count == 0:
            break
        name = r.get("full_name") or r.get("username") or "—"
        medal = medals[i] if i < len(medals) else f"  {i+1}"
        lines.append(T[lang]["leaderboard_row"].format(medal=medal, name=name, count=count))

    lines.append("")
    lines.append(T[lang]["leaderboard_your_rank"].format(rank=rank, count=my_count))

    await message.answer("\n".join(lines))
