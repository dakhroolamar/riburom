const reviewForm = document.getElementById('write-review');
if (reviewForm) {
  document.querySelector('a[href="#write-review"]').addEventListener('click', () => {
    reviewForm.open = true;
  });
  const picker = reviewForm.querySelector('input[type=file]');
  picker.addEventListener('change', () => {
    const files = Array.from(picker.files);
    const total = files.reduce((sum, file) => sum + file.size, 0);
    picker.setCustomValidity(files.length > 3 || total > 12 * 1024 * 1024
      ? 'Choose up to three files totalling 12 MB or less.' : '');
    if (!picker.validity.valid) picker.reportValidity();
  });
}
