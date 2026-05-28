from __future__ import annotations

import asyncio

from aiogram.enums import ChatAction
from aiogram.types import InputMediaPhoto, InputMediaVideo, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.utils.logger import log_error

from .common import album_buffers, last_db_message_id, message_map


async def forward_message_between_chats(
    message: Message, 
    session: AsyncSession,
    target_chat_id: int,
    ticket_id: int,
    sender: str
):
    """Forward message between user and admin with proper formatting and reply support"""
    from app.utils.logger import bot_logger
    bot_logger.info(f"DEBUG: Attempting to forward message from {sender} | Ticket: {ticket_id} | To chat: {target_chat_id} | Type: {message.content_type} | Text: {message.text[:50] if message.text else 'N/A'}")

    reply_to = None
    replied_to = None
    reply_to_message_id = None
    
    # Check if this is a reply to another message
    if message.reply_to_message and message.reply_to_message.message_id:
        reply_source_id = message.reply_to_message.message_id
        
        # Find the corresponding message ID in the other chat
        if (ticket_id, reply_source_id) in message_map:
            reply_to = message_map[(ticket_id, reply_source_id)]
        
        # Try to find the original message in database
        original_msg = await crud.get_ticket_message_by_telegram_id(session, reply_source_id)
        if original_msg:
            replied_to = original_msg.id
    
    # Send typing/upload action to improve UX
    try:
        action = ChatAction.TYPING
        if message.photo:
            action = ChatAction.UPLOAD_PHOTO
        elif message.voice:
            action = ChatAction.RECORD_VOICE
        elif message.document:
            action = ChatAction.UPLOAD_DOCUMENT
        elif message.sticker:
            action = ChatAction.CHOOSE_STICKER
        elif message.animation or message.video:
            action = ChatAction.UPLOAD_VIDEO
        elif message.audio:
            action = ChatAction.UPLOAD_AUDIO
        elif message.video_note:
            action = ChatAction.RECORD_VIDEO_NOTE
        await message.bot.send_chat_action(target_chat_id, action)
    except Exception:
        pass

    # Handle media groups (albums) for photos/videos
    if message.media_group_id and (message.photo or message.video):
        try:
            mgid = str(message.media_group_id)
            key = (ticket_id, target_chat_id, mgid)
            if key not in album_buffers:
                album_buffers[key] = {
                    "items": [],
                    "orig_msg_ids": [],
                    "reply_to": reply_to,
                    "replied_to": replied_to,
                }
                # Schedule flush shortly to gather the group
                async def _flush_after_delay():
                    await asyncio.sleep(1.0)
                    buf = album_buffers.pop(key, None)
                    if not buf:
                        return
                    media: list = []
                    captions: list[str] = []
                    for it in buf["items"]:
                        if it["type"] == "photo":
                            media.append(InputMediaPhoto(media=it["file_id"], caption=it.get("caption") or ""))
                            captions.append(it.get("caption") or "")
                        else:
                            media.append(InputMediaVideo(media=it["file_id"], caption=it.get("caption") or ""))
                            captions.append(it.get("caption") or "")
                    sent_messages = await message.bot.send_media_group(
                        target_chat_id,
                        media,
                        reply_to_message_id=buf["reply_to"]
                    )
                    # Persist and build mapping
                    for idx, sent in enumerate(sent_messages):
                        orig_msg_id = buf["orig_msg_ids"][idx]
                        item = buf["items"][idx]
                        ctype = "photo" if item["type"] == "photo" else "video"
                        text_caption = captions[idx]
                        await crud.add_ticket_message_with_reply(
                            session,
                            ticket_id,
                            sender=sender,
                            content_type=ctype,
                            text=text_caption,
                            telegram_message_id=orig_msg_id,
                            file_id=item["file_id"],
                            reply_to_message_id=buf["reply_to"],
                            replied_to=buf["replied_to"],
                        )
                        message_map[(ticket_id, orig_msg_id)] = sent.message_id
                        message_map[(ticket_id, sent.message_id)] = orig_msg_id
                    bot_logger.info(f"DEBUG: Album forwarding succeeded | Count: {len(sent_messages)} | Ticket: {ticket_id}")

                asyncio.create_task(_flush_after_delay())

            # Append current item
            if message.photo:
                photo = message.photo[-1]
                album_buffers[key]["items"].append({"type": "photo", "file_id": photo.file_id, "caption": message.caption or ""})
            else:
                vid = message.video
                album_buffers[key]["items"].append({"type": "video", "file_id": vid.file_id, "caption": message.caption or ""})
            album_buffers[key]["orig_msg_ids"].append(message.message_id)
            return None
        except Exception as e:
            # Fall back to single send
            log_error(e, {"operation": "album_buffering", "ticket_id": ticket_id})

    try:
        sent_msg = None
        if message.text:
            # Text message
            sent_msg = await message.bot.send_message(
                target_chat_id,
                message.text,
                reply_to_message_id=reply_to
            )
            
            # Save to database
            db_msg = await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="text",
                text=message.text,
                telegram_message_id=message.message_id,
                reply_to_message_id=reply_to,
                replied_to=replied_to
            )
            last_db_message_id[(ticket_id, sender, message.message_id)] = db_msg.id
            
            # Map message IDs for future replies
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
            
        elif message.photo:
            # Photo message (use the largest version)
            photo = message.photo[-1]
            caption = message.caption or ""
            
            sent_msg = await message.bot.send_photo(
                target_chat_id,
                photo.file_id,
                caption=caption,
                reply_to_message_id=reply_to
            )
            
            # Save to database
            db_msg = await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="photo",
                text=caption,
                telegram_message_id=message.message_id,
                file_id=photo.file_id,
                file_unique_id=photo.file_unique_id,
                reply_to_message_id=reply_to,
                replied_to=replied_to
            )
            last_db_message_id[(ticket_id, sender, message.message_id)] = db_msg.id
            
            # Map message IDs for future replies
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
            
        elif message.voice:
            # Voice message
            voice = message.voice
            caption = message.caption or ""
            
            sent_msg = await message.bot.send_voice(
                target_chat_id,
                voice.file_id,
                caption=caption,
                reply_to_message_id=reply_to,
                duration=voice.duration
            )
            
            # Save to database
            db_msg = await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="voice",
                text=caption,
                telegram_message_id=message.message_id,
                file_id=voice.file_id,
                file_unique_id=voice.file_unique_id,
                voice_duration=voice.duration,
                reply_to_message_id=reply_to,
                replied_to=replied_to
            )
            last_db_message_id[(ticket_id, sender, message.message_id)] = db_msg.id
            
            # Map message IDs for future replies
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
            
        elif message.document:
            # Document message
            doc = message.document
            caption = message.caption or ""
            
            sent_msg = await message.bot.send_document(
                target_chat_id,
                doc.file_id,
                caption=caption,
                reply_to_message_id=reply_to
            )
            
            # Save to database
            db_msg = await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="document",
                text=caption,
                telegram_message_id=message.message_id,
                file_id=doc.file_id,
                file_unique_id=doc.file_unique_id,
                file_name=doc.file_name,
                file_size=doc.file_size,
                file_mime_type=doc.mime_type,
                reply_to_message_id=reply_to,
                replied_to=replied_to
            )
            last_db_message_id[(ticket_id, sender, message.message_id)] = db_msg.id
            
            # Map message IDs for future replies
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
        elif message.sticker:
            # Sticker
            stk = message.sticker
            sent_msg = await message.bot.send_sticker(
                target_chat_id,
                stk.file_id,
                reply_to_message_id=reply_to
            )
            await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="sticker",
                text=None,
                telegram_message_id=message.message_id,
                file_id=stk.file_id,
                file_unique_id=getattr(stk, 'file_unique_id', None),
            )
            # Sticker has no meaningful text to edit later
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
        elif message.animation:
            # GIF/animation
            ani = message.animation
            caption = message.caption or ""
            sent_msg = await message.bot.send_animation(
                target_chat_id,
                ani.file_id,
                caption=caption,
                reply_to_message_id=reply_to
            )
            await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="animation",
                text=caption,
                telegram_message_id=message.message_id,
                file_id=ani.file_id,
                file_unique_id=getattr(ani, 'file_unique_id', None),
                file_size=getattr(ani, 'file_size', None),
                file_mime_type=getattr(ani, 'mime_type', None),
            )
            last_db_message_id[(ticket_id, sender, message.message_id)] = db_msg.id if 'db_msg' in locals() else last_db_message_id.get((ticket_id, sender, message.message_id), 0)
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
        elif message.video:
            vid = message.video
            caption = message.caption or ""
            sent_msg = await message.bot.send_video(
                target_chat_id,
                vid.file_id,
                caption=caption,
                reply_to_message_id=reply_to
            )
            await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="video",
                text=caption,
                telegram_message_id=message.message_id,
                file_id=vid.file_id,
                file_unique_id=getattr(vid, 'file_unique_id', None),
                file_size=getattr(vid, 'file_size', None),
                file_mime_type=getattr(vid, 'mime_type', None),
            )
            last_db_message_id[(ticket_id, sender, message.message_id)] = db_msg.id if 'db_msg' in locals() else last_db_message_id.get((ticket_id, sender, message.message_id), 0)
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
        elif message.audio:
            aud = message.audio
            caption = message.caption or ""
            sent_msg = await message.bot.send_audio(
                target_chat_id,
                aud.file_id,
                caption=caption,
                reply_to_message_id=reply_to
            )
            await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="audio",
                text=caption,
                telegram_message_id=message.message_id,
                file_id=aud.file_id,
                file_unique_id=getattr(aud, 'file_unique_id', None),
                file_size=getattr(aud, 'file_size', None),
                file_mime_type=getattr(aud, 'mime_type', None),
            )
            last_db_message_id[(ticket_id, sender, message.message_id)] = db_msg.id if 'db_msg' in locals() else last_db_message_id.get((ticket_id, sender, message.message_id), 0)
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
        elif message.video_note:
            vn = message.video_note
            sent_msg = await message.bot.send_video_note(
                target_chat_id,
                vn.file_id,
                reply_to_message_id=reply_to
            )
            await crud.add_ticket_message_with_reply(
                session,
                ticket_id,
                sender=sender,
                content_type="video_note",
                telegram_message_id=message.message_id,
                file_id=vn.file_id,
                file_unique_id=getattr(vn, 'file_unique_id', None),
            )
            # No text to sync
            message_map[(ticket_id, message.message_id)] = sent_msg.message_id
            message_map[(ticket_id, sent_msg.message_id)] = message.message_id
            bot_logger.info(f"DEBUG: Forwarding succeeded | Sent message ID: {sent_msg.message_id} | Ticket: {ticket_id}")
            return sent_msg
        else:
            # Unsupported message type
            await message.reply("این نوع پیام پشتیبانی نمی‌شود.")
            bot_logger.info(f"DEBUG: Forwarding failed | Unsupported type for Ticket: {ticket_id}")
            return None
    except Exception as e:
        log_error(e, {"operation": "forward_private_chat_message", "ticket_id": ticket_id})
        bot_logger.error(f"DEBUG: Forwarding failed | Error: {str(e)} | Ticket: {ticket_id}")
        await message.reply("خطا در ارسال پیام")
        return None
