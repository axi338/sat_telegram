from urllib.parse import quote

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

import database as db
from config import BOT_USERNAME, REQUIRED_REFERRALS
from services.channel_checker import check_all_channels
from services.file_service import deliver_reward, progress_bar


def build_referral_link(telegram_id: int) -> str:
    username = BOT_USERNAME or "your_bot"
    return f"https://t.me/{username}?start=ref_{telegram_id}"


def build_share_url(referral_link: str) -> str:
    share_text = (
        "DTM topshirib, har yili grant uchun asab buzishdan charchadingizmi?\n\n"
        "Ko'pchilik bilmaydigan haqiqat: DTM orqali kirsangiz, davlat granti atigi 1 yilga beriladi — har yili GPA deb yugurasiz.\n\n"
        "Bitta SAT bilan esa:\n\n"
        "• O'zbekistondagi nufuzli universitetlarda (JIDU, TDIU) 4 yillik kafolatlangan grant yutasiz.\n"
        "• Xorijda esa $300,000+ lik Full-ride (kontrakt + yotoqxona + stipendiya) olish mumkin.\n\n"
        "🎁 SAT'ni 0 dan boshlayotganlar uchun to'liq bepul video kurs va materiallar ochildi.\n\n"
        "🎁 Sovg'alar (eng ko'p do'st chaqirganlarga):\n\n"
        "🥇 1-o'rin: 500,000 so'm\n"
        "🥈 2-o'rin: 300,000 so'm\n"
        "🥉 3-o'rin: 100,000 so'm\n\n"
        "Kursni olish va 500,000 so'mgacha naqd pul yutish uchun botga kiring:\n\n"
        f"👉 {referral_link}\n"
        f"👉 {referral_link}\n"
        f"👉 {referral_link}"
    )
    return (
        "https://t.me/share/url?"
        f"url={quote(referral_link, safe='')}"
        f"&text={quote(share_text, safe='')}"
    )


def parse_referral_payload(start_payload: str | None) -> int | None:
    if not start_payload:
        return None
    raw = start_payload.strip()
    if raw.startswith("ref_"):
        raw = raw[4:]
    if raw.isdigit():
        return int(raw)
    return None


async def process_referral_start(
    new_user_id: int,
    start_payload: str | None,
) -> int | None:
    """
    Assign referral ownership for a brand-new bot user only.
    Credit happens later after all 3 channels are verified.
    """
    inviter_id = parse_referral_payload(start_payload)
    if not inviter_id or inviter_id == new_user_id:
        return None

    inviter = await db.get_user(inviter_id)
    if not inviter:
        return None

    return inviter_id


def inviter_success_message(referral_count: int) -> str:
    remaining = max(REQUIRED_REFERRALS - referral_count, 0)
    bar = progress_bar(referral_count)

    if referral_count == 1:
        return (
            "🎉 <b>New friend added!</b>\n\n"
            "Your referral has been successfully verified.\n\n"
            f"<b>Progress: {referral_count} / {REQUIRED_REFERRALS}</b>\n"
            f"{bar}\n\n"
            f"Only <b>{remaining} more friends</b> to go!\n\n"
            "Keep sharing your link."
        )
    if referral_count >= REQUIRED_REFERRALS:
        return (
            "🔥 <b>2 / 3 friends completed!</b>\n\n"
            f"{bar}\n\n"
            "You're one step away from unlocking your "
            "<b>SAT Full Course</b> access.\n\n"
            "Invite <b>1 more friend</b> who joins all 4 channels."
        )
    return (
        "🎉 <b>New friend added!</b>\n\n"
        "Your referral has been successfully verified.\n\n"
        f"<b>Progress: {referral_count} / {REQUIRED_REFERRALS}</b>\n"
        f"{bar}"
    )


def referred_user_viral_loop_message(referral_link: str) -> str:
    return (
        "✅ <b>Membership confirmed!</b>\n\n"
        "You've helped your friend move closer to their SAT Full Course access.\n\n"
        "🎁 <b>Want free access yourself?</b>\n\n"
        "Invite <b>3 friends</b> who open this bot through your link and join all "
        "4 required channels — your personal access link unlocks automatically.\n\n"
        f"<b>Your personal invite link:</b>\n{referral_link}"
    )


async def check_and_credit_referral(bot: Bot, user_id: int) -> bool:
    """
    Credit inviter only after referred user joins all 3 channels.
    Permanent credit — never revoked if user later leaves a channel.
    """
    user = await db.get_user(user_id)
    if not user or not user.get("invited_by") or user.get("referral_credited"):
        return False

    if not await check_all_channels(bot, user_id):
        return False

    inviter_id = user["invited_by"]
    credited, new_count = await db.credit_referral(inviter_id, user_id)
    if not credited:
        return False

    try:
        if new_count >= REQUIRED_REFERRALS:
            await deliver_reward(bot, inviter_id)
        else:
            await bot.send_message(inviter_id, inviter_success_message(new_count))
    except TelegramAPIError:
        pass

    try:
        ref_link = build_referral_link(user_id)
        from keyboards import dashboard_keyboard

        await bot.send_message(
            user_id,
            referred_user_viral_loop_message(ref_link),
            reply_markup=dashboard_keyboard(user_id),
        )
    except TelegramAPIError:
        pass

    return True


def referrals_complete(referral_count: int) -> bool:
    return referral_count >= REQUIRED_REFERRALS
