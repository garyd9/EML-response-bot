import discord


class QuestionPromptViewExampleUsage:
    """This class exists to keep its code out of the global namespace. It should not be used.

    It is a valid class to keep syntax highlighting and ensure continued accuracy through breaking changes.
    If not for these puropses, this would just be a large comment block with the examples.
    """

    def __init__(self):
        raise NotImplementedError(f"{type(self).__name__} should not be instantiated.")

    ########################################
    ### QuestionPromptView Usage Example ###
    ########################################
    async def example_question_prompt_with_button_options(
        interaction: discord.Interaction,
    ):
        options_dict = {
            "option1": "Option 1",
            "option2": "Option 2",
            "option3": "Option 3",
        }
        view = QuestionPromptView(options_dict=options_dict)
        await interaction.response.send_message("Which option?", view=view)
        await view.wait()
        await interaction.followup.send(f"You selected: {view.value}")


class QuestionOptionButton(discord.ui.Button):
    """A button for a multiple choice question of type `QuestionPromptView`

    Args:
        label (str): The text displayed on the button
        custom_id (str): The value returned when the button is selected

    Notes:
        Calls `QuestionPromptView.select()` to handle the button selection
        This depends on `custom_id` to determine the selected value


    Example: QuestionOptionButton("Option 1", "option1")
    Result: A button with the label "Option 1" and the value "option1"
    """

    def __init__(self, label: str, custom_id: str):
        super().__init__(
            label=label, custom_id=custom_id, style=discord.ButtonStyle.secondary
        )
        self.view: QuestionPromptView

    async def callback(self, interaction: discord.Interaction):
        await self.view.select(interaction, self)


class QuestionPromptView(discord.ui.View):
    """Question prompt with multiple choice options of type `QuestionOptionButton`

    Args:
        timeout (int): The time in seconds before the view times out
        options_dict (dict): A dictionary of options to display
        default_value (str): The default value to return if no option is selected

    Returns:
        self.value (str): The value of the selected option
        self.label (str): The button text of the selected option

    Example Usage:
        interaction: discord.Interaction
        options_dict = {
            "option1": "Option 1",
            "option2": "Option 2",
            "option3": "Option 3",
        }
        view = QuestionPromptView(options_dict=options_dict)
        await interaction.response.send_message("Which option?", view=view)
        await view.wait()
        await interaction.followup.send(f"You selected: {view.value}")

    Result:
        "Option 1", "Option 2", and "Option 3" are displayed as buttons.
        "option1", "option2", or "option3" are the associated values respectively.
    """

    def __init__(
        self, *, timeout=180, options_dict: dict = {}, default_value: str = None
    ):
        super().__init__(timeout=timeout)
        self.value = default_value
        # Add buttons for each option
        for option_id, option_label in options_dict.items():
            self.add_item(QuestionOptionButton(custom_id=option_id, label=option_label))

    async def select(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Make the name and value of the selected button available
        self.label = button.label
        self.value = button.custom_id if button.custom_id else button.label
        # Update the selected button
        button.style = discord.ButtonStyle.success
        # Disable all buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        # Update the message view to reflect these changes
        await interaction.response.edit_message(view=self)
        # Stop the view, picked up by `await view.wait()` in the calling function
        self.stop()
