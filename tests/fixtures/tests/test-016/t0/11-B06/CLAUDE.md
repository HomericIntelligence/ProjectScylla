### Key Development Principles

1. KISS - *K*eep *I*t *S*imple *S*tupid -> Don't add complexity when a simpler solution works
1. YAGNI - *Y*ou *A*in't *G*onna *N*eed *I*t -> Don't add things until they are required
1. TDD - *T*est *D*riven *D*evelopment -> Write tests to drive the implementation
1. DRY - *D*on't *R*epeat *Y*ourself -> Don't duplicate functionality, data structures, or algorithms
1. SOLID - *S**O**L**I**D* ->
  . Single Responsibility
  . Open-Closed
  . Liskov Substitution
  . Interface Segregation
  . Dependency Inversion
1. Modularity - Develop independent modules through well defined interfaces
1. POLA - *P*rinciple *O*f *L*east *A*stonishment - Create intuitive and predictable interfaces to not surprise users

Relevant links:

- [Core Principles of Software Development](<https://softjourn.com/insights/core-principles-of-software-development>)
- [7 Common Programming Principles](<https://www.geeksforgeeks.org/blogs/7-common-programming-principles-that-every-developer-must-follow/>)
- [Software Development Principles](<https://coderower.com/blogs/software-development-principles-software-engineering>)
- [Clean Coding Principles](<https://www.pullchecklist.com/posts/clean-coding-principles>)

### Documentation Rules

- **Issue-specific outputs**: Post as comments on the GitHub issue using `gh issue comment <number>`
- **Developer documentation**: `/docs/dev/` (architectural decisions, design docs)
- **Team guides**: `/agents/` (quick start, hierarchy, templates)
- **Never duplicate** documentation across locations - link instead
- See `.claude/shared/github-issue-workflow.md` for GitHub issue read/write patterns
