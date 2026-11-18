const editor = document.querySelector('.invoice-sheet');
function refreshRows() {
  const rows = editor.querySelectorAll('#lines [data-row]');
  for (const row of rows) {
    row.querySelector('[data-remove]').disabled = rows.length === 1;
    row.querySelector('[name=gst]').readOnly = editor.elements.mode.value === 'No GST';
    row.querySelector('[name=qty]').min = '0.01';
    row.querySelector('[name=gst]').max = '100';
  }
}
editor.addEventListener('click', event => {
  const action = event.target.closest('button');
  if (!action) return;
  if (action.dataset.add) {
    const group = document.getElementById(action.dataset.add);
    group.append(document.getElementById(group.id + '-template').content.cloneNode(true));
    group.lastElementChild.querySelector('input,textarea').focus();
  }
  if (action.hasAttribute('data-remove')) action.closest('[data-row]').remove();
  refreshRows();
});
editor.elements.mode.addEventListener('change', refreshRows);
refreshRows();
