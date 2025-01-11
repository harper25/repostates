gone remotes - shows as correct which is invalid

fix checkout to nonexistent branch - no info unless -v WARNING
same check pull in nonexistent remote

find branch name or tag name
git name-rev --name-only HEAD
git name-rev --tags --name-only $(git rev-parse HEAD)
if on tag - pulling is not possible nor needed
https://stackoverflow.com/questions/6245570/how-do-i-get-the-current-branch-name-in-git
git describe --all
git branch | sed -n '/\* /s///p'
git describe --tags --exact-match || git symbolic-ref --short HEAD


git rev-list --count --left-right feature/PHXA-41229-resource-cleaner-update...remotes/origin/feature/PHXA-41229-resource-cleaner-update

