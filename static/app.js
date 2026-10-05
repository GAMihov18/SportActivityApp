document.querySelectorAll('[data-open]').forEach(button => {
  button.addEventListener('click', () => document.getElementById(button.dataset.open).showModal());
});
document.querySelectorAll('[data-close]').forEach(button => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('click', event => {
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close();
    }
  });
});
document.querySelectorAll('[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => { if (!confirm(form.dataset.confirm)) event.preventDefault(); });
});
const search = document.getElementById('search');
const sport = document.getElementById('sport-filter');
function filterCards() {
  let visible = 0;
  const cards = document.querySelectorAll('.searchable');
  cards.forEach(card => {
    const matches = card.textContent.toLocaleLowerCase().includes(search.value.toLocaleLowerCase()) && (!sport.value || card.dataset.sport === sport.value);
    card.hidden = !matches;
    if (matches) visible++;
  });
  document.getElementById('no-results').hidden = visible > 0 || cards.length === 0;
}
if (search && sport) { search.addEventListener('input', filterCards); sport.addEventListener('change', filterCards); }
