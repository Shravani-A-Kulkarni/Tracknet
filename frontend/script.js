document.addEventListener("DOMContentLoaded", () => {
  const contactForm = document.getElementById("contactForm");
  if (contactForm) {
    contactForm.addEventListener("submit", (e) => {
      e.preventDefault();

      alert(
        "Thank you! Your message has been sent successfully. We will get back to you shortly."
      );
      e.target.reset();
    });
  }

  const exploreBtn = document.getElementById("exploreBtn");
  if (exploreBtn) {
    exploreBtn.addEventListener("click", () => {
      window.location.href = "features.html";
    });
  }
});
