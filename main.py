
import functions

if __name__ == "__main__":
    keep_running = True

    while keep_running:
        functions.show_main_menu()
        try:
            user_input = int(input("Choose an option: "))
        except ValueError:
            print("Please enter a valid number.")
            continue

        # Execute the chosen function
        functions.get_user_choice(user_input)

        # Ask if the user wants to continue
        answer = input("Do you want to continue? (Y/N): ").strip().upper()
        if answer != "Y":
            print("Exiting...")
            keep_running = False
