const storyCard = document.querySelector('.rb-story-notification');
if (storyCard) {
  const key = storyCard.dataset.storyKey;
  try {storyCard.hidden = localStorage.getItem('riburom-dismissed-story') === key;}
  catch {storyCard.hidden = false;}
  storyCard.querySelector('.rb-story-notification-close')?.addEventListener('click', () => {
    storyCard.hidden = true;
    try {localStorage.setItem('riburom-dismissed-story', key);} catch { /* Storage can be unavailable in private sessions. */ }
  });
}
