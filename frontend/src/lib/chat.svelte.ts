// A "new chat" click in the sidebar needs to reset the chat page's local
// state even when already on `/` (a same-route navigation doesn't remount
// the page component on its own). This tiny shared signal is the
// lowest-friction way to say "clear the thread" across that layout/page
// boundary without lifting the whole conversation into a store.
export const chatReset = $state({ token: 0 });

export function requestNewChat() {
	chatReset.token++;
}
