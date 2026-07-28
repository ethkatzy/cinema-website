document.querySelectorAll(".wizard-seat").forEach(cell => {
    cell.addEventListener("click", () => {
        const paintType = document.querySelector('input[name="paint-type"]:checked').value;
        cell.dataset.type = paintType;
        cell.className = `wizard-seat type-${paintType.toLowerCase()}`;
    });
});

document.getElementById("edit-form").addEventListener("submit", () => {
    const layout = Array.from(document.querySelectorAll(".wizard-seat")).map(cell => ({
        seatid: parseInt(cell.dataset.seatid, 10),
        type: cell.dataset.type,
    }));
    document.getElementById("layout_json").value = JSON.stringify(layout);
});
