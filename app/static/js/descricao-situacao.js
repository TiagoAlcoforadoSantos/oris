document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".js-situacao-select").forEach((select) => {
        const form = select.closest("form");
        const description = form?.querySelector(".js-descricao-situacao");
        if (!description) {
            return;
        }

        const toggleDescription = () => {
            description.hidden = !["INATIVA", "INATIVO", "MANUTENCAO"].includes(select.value);
        };

        select.addEventListener("change", toggleDescription);
        toggleDescription();
    });
});
