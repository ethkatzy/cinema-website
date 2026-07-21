const ROW_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

const wizard = document.getElementById("wizard");
const maxRows = parseInt(wizard.dataset.maxRows, 10);
const maxCols = parseInt(wizard.dataset.maxCols, 10);

let seats = [];
let rowsList = [];
let cols = 0;

function showStep(stepId) {
    document.querySelectorAll(".wizard-step").forEach(step => {
        step.hidden = step.id !== stepId;
    });
}

function setError(elementId, message) {
    document.getElementById(elementId).textContent = message;
}

function renderGrid(container, mode) {
    container.innerHTML = "";
    container.style.gridTemplateColumns = `repeat(${cols + 1}, auto)`;

    const corner = document.createElement("div");
    corner.className = "wizard-label";
    corner.style.gridRow = 1;
    corner.style.gridColumn = 1;
    container.appendChild(corner);

    for (let col = 1; col <= cols; col++) {
        const label = document.createElement("div");
        label.className = "wizard-label";
        label.textContent = col;
        label.style.gridRow = 1;
        label.style.gridColumn = col + 1;
        container.appendChild(label);
    }

    rowsList.forEach((row, rowIndex) => {
        const label = document.createElement("div");
        label.className = "wizard-label";
        label.textContent = row;
        label.style.gridRow = rowIndex + 2;
        label.style.gridColumn = 1;
        container.appendChild(label);
    });

    seats.forEach((seat, index) => {
        if (mode === "paint" && !seat.exists) {
            return;
        }
        const cell = document.createElement("button");
        cell.type = "button";
        cell.className = "wizard-seat";
        cell.style.gridRow = rowsList.indexOf(seat.row) + 2;
        cell.style.gridColumn = seat.col + 1;
        cell.title = `${seat.row}${seat.col}`;

        if (mode === "remove") {
            cell.classList.toggle("removed", !seat.exists);
            cell.addEventListener("click", () => {
                seats[index].exists = !seats[index].exists;
                renderGrid(container, "remove");
            });
        } else {
            cell.classList.add(`type-${seat.type.toLowerCase()}`);
            cell.addEventListener("click", () => {
                const paintType = document.querySelector('input[name="paint-type"]:checked').value;
                seats[index].type = paintType;
                cell.className = `wizard-seat type-${paintType.toLowerCase()}`;
            });
        }

        container.appendChild(cell);
    });
}

document.getElementById("generate-grid-btn").addEventListener("click", () => {
    const rows = parseInt(document.getElementById("rows-input").value, 10);
    const colCount = parseInt(document.getElementById("cols-input").value, 10);

    if (!Number.isInteger(rows) || rows < 1 || rows > maxRows
        || !Number.isInteger(colCount) || colCount < 1 || colCount > maxCols) {
        setError("step-1-error", `Enter between 1 and ${maxRows} rows and 1 and ${maxCols} columns.`);
        return;
    }
    setError("step-1-error", "");

    cols = colCount;
    rowsList = ROW_LETTERS.slice(0, rows).split("");
    seats = [];
    rowsList.forEach(row => {
        for (let col = 1; col <= cols; col++) {
            seats.push({ row, col, exists: true, type: "Regular" });
        }
    });

    renderGrid(document.getElementById("step-2-grid"), "remove");
    showStep("step-2");
});

document.getElementById("to-step-3-btn").addEventListener("click", () => {
    if (!seats.some(seat => seat.exists)) {
        setError("step-2-error", "At least one seat must remain.");
        return;
    }
    setError("step-2-error", "");
    renderGrid(document.getElementById("step-3-grid"), "paint");
    showStep("step-3");
});

document.querySelectorAll("[data-back-to]").forEach(button => {
    button.addEventListener("click", () => showStep(button.dataset.backTo));
});

document.getElementById("screen-form").addEventListener("submit", () => {
    const layout = seats
        .filter(seat => seat.exists)
        .map(seat => ({ row: seat.row, col: seat.col, type: seat.type }));
    document.getElementById("layout_json").value = JSON.stringify(layout);
});
