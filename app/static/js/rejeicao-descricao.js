document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".js-form-rejeicao").forEach((form) => {
        const revealButton = form.querySelector(".js-show-rejection");
        const details = form.querySelector(".js-rejection-details");
        const cancelButton = form.querySelector(".js-cancel-rejection");
        const description = details?.querySelector("textarea");

        revealButton?.addEventListener("click", () => {
            details.hidden = false;
            revealButton.hidden = true;
            description?.focus();
        });

        cancelButton?.addEventListener("click", () => {
            details.hidden = true;
            revealButton.hidden = false;
            if (description) {
                description.value = "";
            }
        });
    });
});
