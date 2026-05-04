# CS10 Arcade Game Template

This repository is a template for small student teams building a 2D game with Python and Arcade.

## Getting Started with Your Team

### Step 1: One student creates the team repository

1. **Copy the template**: Click the "Use this template" button on GitHub to create your team's copy
2. **Give it a team name**: Name it something like `cs10-game-projectname`

### Step 2: Add collaborators to the repository

**Option A: Using GitHub web UI**

1. Go to your new repository's **Settings**
2. Select **Collaborators** (or **Access** on newer GitHub)
3. Click **Add people**
4. Search for and invite each teammate by GitHub username
5. Each teammate will receive an invitation to accept

**Option B: Using GitHub CLI**

For each teammate, run:

```bash
gh repo collaborator add <github-username> --permission push
```

### Step 3: Each student clones the repository locally

Each team member should:

1. Open a new Terminal

2. Clone the team's project repo (aka download a copy of the project's files to your computer)

```bash
gh repo clone your-team/cs10-game-projectname
```

3. Open that project folder in VS Code

```bash
code cs10-game-projectname
```

If that doesn't work, do this:

```bash
open cs10-game-projectname
```

That will show you where the project folder is. 

Go back to VSCode, do **File** >> **Open Folder** >> choose that project folder

### Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Each student creates their own working file

Each team member creates their own file with their name. For example:
- Rosa creates: `game-rosa.py`
- Aryan creates: `game-aryan.py`
- Alex creates: `game-alex.py`

Start by copying the example from `game.py` or create your own UI element to add.

### Step 6: Test that everything works

Run the main game file to verify setup:

```bash
python game.py
```

## How to Work Together

### Daily workflow

**Before you start coding:**
```bash
git pull
```

**After you finish coding:**
```bash
git push
```

### The game.py owner role

One person is assigned as the **game.py owner for the day**:
- They integrate everyone's work from `game-yourname.py` files into `game.py`
- Everyone else only edits their own `game-yourname.py` file
- Switch owners each day to share responsibility

### File ownership rules

- **Only the owner** edits `game.py` directly
- **Everyone else** edits only their own `game-yourname.py` file
- Always keep your personal file up to date in git

### If there's a merge conflict (multiple people edited the same file)

1. Git will tell you there's a conflict
2. Ask your team for help or use AI to resolve it
3. Ask Mr. Sharp

## More Details

See [`COLLAB.md`](COLLAB.md) for detailed collaboration guidelines.
