app_name = "xal_chatbot"
app_title = "XAL Accountant Bot"
app_publisher = "XAL Finance"
app_description = "An accountant chatbot inside ERPNext"
app_email = "noreply@example.com"
app_license = "mit"

# The chat button, shown only to users allowed to use the bot (see api.get_boot).
app_include_js = "/assets/xal_chatbot/js/accountant_bot.js"
app_include_css = "/assets/xal_chatbot/css/accountant_bot.css"

after_install = "xal_chatbot.install.after_install"
