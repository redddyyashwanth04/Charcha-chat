const DAY = 24 * 60 * 60 * 1000;

function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** Group conversations (already sorted by recency) like Claude/ChatGPT do. */
export function groupByDate(conversations, now = new Date()) {
  const today = startOfDay(now);
  const groups = [
    { label: "Pinned", items: [] },
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Previous 30 days", items: [] },
    { label: "Older", items: [] },
  ];
  for (const c of conversations) {
    if (c.pinned) {
      groups[0].items.push(c);
      continue;
    }
    const age = today - startOfDay(new Date(c.updated_at));
    if (age <= 0) groups[1].items.push(c);
    else if (age <= DAY) groups[2].items.push(c);
    else if (age <= 7 * DAY) groups[3].items.push(c);
    else if (age <= 30 * DAY) groups[4].items.push(c);
    else groups[5].items.push(c);
  }
  return groups.filter((g) => g.items.length > 0);
}
