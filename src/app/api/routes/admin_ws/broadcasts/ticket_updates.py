"""Broadcast ticket detail and admin ticket-list WebSocket updates."""

import time
from weakref import WeakSet

from ..state import (
    CONNECTION_TIMEOUT,
    active_connections,
    admin_connections,
    connection_health,
    logger,
    user_connection_map,
    user_connections,
)


async def broadcast_ticket_update(ticket_id: int, update_type: str, data: dict = None, ticket_user_id: int = None):
    """
    Broadcast an update to all connections watching a specific ticket.
    For 'new_message' updates, also broadcasts to the ticket owner's connection
    (if they're connected but not watching the ticket) so they see updates in their ticket list.
    
    Call this from admin.py when:
    - New message is added to ticket
    - Ticket status changes
    
    Args:
        ticket_id: The ticket ID
        update_type: 'new_message', 'status_change', etc.
        data: Optional additional data
        ticket_user_id: The user_id who owns this ticket (required for 'new_message' to avoid broadcasting to all users)
    """
    message = {
        'type': update_type,
        'ticket_id': ticket_id,
        'data': data or {}
    }
    
    current_time = time.time()
    dead_connections = []
    
    # Get connections watching this ticket (both admin and user)
    watchers = active_connections.get(ticket_id, WeakSet())
    sent_to_connections = set()  # Track which connections we've already sent to
    
    # Broadcast to connections watching this specific ticket
    for ws in list(watchers):
        try:
            # Check if connection is still alive
            if ws.closed:
                dead_connections.append(ws)
                continue
            
            # Check connection health (timeout)
            last_activity = connection_health.get(ws, 0)
            if current_time - last_activity > CONNECTION_TIMEOUT:
                logger.warning(f'WebSocket connection timed out, removing')
                dead_connections.append(ws)
                continue
            
            # Send message
            await ws.send_json(message)
            connection_health[ws] = current_time  # Update activity time
            sent_to_connections.add(id(ws))  # Track that we sent to this connection
            
        except Exception as e:
            logger.warning(f'Failed to send WebSocket message: {e}')
            dead_connections.append(ws)
    
    # Clean up dead connections from watchers
    for dead_ws in dead_connections:
        watchers.discard(dead_ws)
        connection_health.pop(dead_ws, None)
    
    # For important updates, also broadcast to the ticket owner's connection
    # (if they're connected but not watching the ticket) so they see updates in their ticket list.
    # - new_message: update preview + unread
    # - status_change: update status badge immediately
    if update_type in ('new_message', 'status_change') and ticket_user_id:
        dead_user_connections = []
        for ws in list(user_connections):
            try:
                # Skip if we already sent to this connection (it's watching the ticket)
                if id(ws) in sent_to_connections:
                    continue
                
                # Only send to the ticket owner's connection
                ws_user_id = user_connection_map.get(ws)
                if ws_user_id != ticket_user_id:
                    continue
                
                # Check if connection is still alive
                if ws.closed:
                    dead_user_connections.append(ws)
                    continue
                
                # Check connection health (timeout)
                last_activity = connection_health.get(ws, 0)
                if current_time - last_activity > CONNECTION_TIMEOUT:
                    dead_user_connections.append(ws)
                    continue
                
                # Send message to ticket owner's connection
                await ws.send_json(message)
                connection_health[ws] = current_time
                
            except Exception as e:
                logger.warning(f'Failed to send WebSocket message to user connection: {e}')
                dead_user_connections.append(ws)
        
        # Clean up dead user connections
        for dead_ws in dead_user_connections:
            user_connections.discard(dead_ws)
            user_connection_map.pop(dead_ws, None)
            connection_health.pop(dead_ws, None)


async def broadcast_ticket_list_update():
    """
    Broadcast to all admins that the ticket list has changed.
    (New ticket created, ticket closed, etc.)
    
    Frontend will refetch the ticket list when it receives this.
    """
    message = {
        'type': 'tickets_updated'
    }
    
    current_time = time.time()
    dead_connections = []
    
    for ws in list(admin_connections):
        try:
            # Check if connection is still alive
            if ws.closed:
                dead_connections.append(ws)
                continue
            
            # Check connection health
            last_activity = connection_health.get(ws, 0)
            if current_time - last_activity > CONNECTION_TIMEOUT:
                dead_connections.append(ws)
                continue
            
            # Send message
            await ws.send_json(message)
            connection_health[ws] = current_time
            
        except Exception as e:
            logger.warning(f'Failed to broadcast ticket list update: {e}')
            dead_connections.append(ws)
    
    # Clean up dead connections
    for dead_ws in dead_connections:
        admin_connections.discard(dead_ws)
        connection_health.pop(dead_ws, None)

