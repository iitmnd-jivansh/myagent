/**
 * MyAgent Frontend Supabase Client
 * 
 * Provides real-time message subscriptions from Supabase.
 * Uses the anon/public key (safe for client-side use).
 * 
 * Configure via the SUPABASE_CONFIG global variable set in index.html.
 */

const SUPABASE_CONFIG = window.SUPABASE_CONFIG || {};

/**
 * Create a Supabase client instance.
 * Falls back gracefully if no config is provided.
 */
function createSupabaseClient() {
  const { url, anonKey } = SUPABASE_CONFIG;
  if (!url || !anonKey) {
    console.warn('[Supabase] Not configured — real-time subscriptions disabled');
    return null;
  }
  try {
    const supabase = window.supabase.createClient(url, anonKey, {
      realtime: {
        params: {
          eventsPerSecond: 10,
        },
      },
    });
    console.log('[Supabase] Client initialized');
    return supabase;
  } catch (err) {
    console.error('[Supabase] Failed to initialize:', err);
    return null;
  }
}

/** Singleton supabase client instance */
let _supabaseClient = null;

function getSupabaseClient() {
  if (_supabaseClient === null) {
    _supabaseClient = createSupabaseClient();
  }
  return _supabaseClient;
}

/**
 * Subscribe to new messages for a conversation.
 * Calls onMessage for each new message received.
 * Returns an unsubscribe function.
 * 
 * @param {number} conversationId - The conversation ID to subscribe to
 * @param {function} onMessage - Callback receiving the message object
 * @returns {function} unsubscribe function
 */
export function subscribeToMessages(conversationId, onMessage) {
  const supabase = getSupabaseClient();
  if (!supabase) {
    console.warn('[Supabase] Cannot subscribe — not configured');
    return () => {};
  }

  const channel = supabase
    .channel(`messages:${conversationId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'messages',
        filter: `conversation_id=eq.${conversationId}`,
      },
      (payload) => {
        console.log('[Supabase] New message received via Realtime:', payload.new.id);
        onMessage(payload.new);
      }
    )
    .subscribe();

  console.log(`[Supabase] Subscribed to messages for conversation #${conversationId}`);

  // Return unsubscribe function
  return () => {
    console.log(`[Supabase] Unsubscribed from conversation #${conversationId}`);
    supabase.removeChannel(channel);
  };
}