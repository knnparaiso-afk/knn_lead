const phone = document.getElementById("whatsapp");
phone?.addEventListener("input", () => {
  const digits = phone.value.replace(/\D/g, "").slice(0, 11);
  phone.value = digits.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2");
});
document.querySelector(".lead-form")?.addEventListener("submit", (event) => {
  const button = event.currentTarget.querySelector("button[type=submit]");
  if (button) { button.disabled = true; button.textContent = "Enviando seu cadastro…"; }
});
