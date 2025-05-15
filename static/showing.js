document.querySelectorAll('.seat').forEach(label => {
    label.addEventListener('click', function () {
        const checkbox = this.querySelector('input[type="checkbox"]');
        checkbox.checked = !checkbox.checked;
        this.classList.toggle('selected', checkbox.checked);
    });
});