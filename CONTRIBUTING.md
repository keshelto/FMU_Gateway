# Contributing to FMU Gateway

Thank you for your interest in contributing! 🎉

## Ways to Contribute

### 🐛 Report Bugs
- Check [existing issues](../../issues) first
- Provide clear reproduction steps
- Include environment details (OS, Python version, etc.)
- Share error logs and stack traces

### 💡 Suggest Features
- Open a [discussion](../../discussions) for new ideas
- Explain the use case and benefits
- Consider backward compatibility
- Propose implementation approach

### 🔧 Submit Code
- Fork the repository
- Create a feature branch (`git checkout -b feature/amazing-feature`)
- Write tests for new functionality
- Follow existing code style
- Update documentation as needed
- Submit a pull request

### 📖 Improve Documentation
- Fix typos and unclear explanations
- Add examples and use cases
- Improve API documentation
- Translate to other languages

## Development Setup

### Local Development

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/FMU_Gateway.git
cd FMU_Gateway

# Install dependencies
pip install -r requirements.txt
pip install -e ./sdk/python

# Run tests
pytest tests/

# Start local server
uvicorn app.main:app --reload
```

### Environment Variables

For local development, create a `.env` file:

```bash
STRIPE_ENABLED=false  # Disable payments for testing
REQUIRE_AUTH=false    # Disable auth for testing
DATABASE_URL=sqlite:///./local.db
```

## Code Standards

### Python Style
- Follow PEP 8
- Use type hints where helpful
- Keep functions focused and testable
- Add docstrings for public APIs

### Testing
- Write tests for new features
- Maintain test coverage
- Use pytest fixtures for common setup
- Test both success and error cases

### Commit Messages
- Use clear, descriptive messages
- Reference issues when applicable
- Follow conventional commits (optional):
  - `feat:` New feature
  - `fix:` Bug fix
  - `docs:` Documentation
  - `test:` Tests
  - `refactor:` Code refactoring

## Pull Request Process

1. **Update documentation** if adding features
2. **Add tests** for new functionality
3. **Ensure tests pass** (`pytest tests/`)
4. **Update CHANGELOG** (if applicable)
5. **Submit PR** with clear description

### PR Checklist

- [ ] Code follows project style
- [ ] Tests added and passing
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Commits are clean and well-described

## Areas We'd Love Help With

### High Priority
- 🧪 More test coverage (especially payment flows)
- 📝 Documentation improvements
- 🐛 Bug fixes and edge cases
- 🔒 Security enhancements

### Feature Ideas
- 📊 Analytics dashboard
- 🎨 Web UI for simulations
- 🔌 Additional integrations (GitHub Actions, CI/CD)
- 📦 More FMU library models
- 🌍 Internationalization
- 🎯 Performance optimizations

### Lower Priority
- 🎨 UI/UX improvements
- 📱 Mobile-friendly docs
- 🎓 Tutorials and guides
- 🔧 Developer tooling

## Questions?

- **General Questions:** Open a [discussion](../../discussions)
- **Bug Reports:** Open an [issue](../../issues)
- **Security Issues:** Email (don't open public issue)

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community
- Show empathy

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Public or private harassment
- Publishing others' private information
- Other unprofessional conduct

## License

By contributing, you agree that your contributions will be licensed under the MIT License (for the code).

Note: The hosted API service and FMU library are commercial offerings. Your code contributions do not grant rights to these commercial services.

## Recognition

Contributors will be:
- Listed in release notes
- Credited in documentation
- Thanked publicly (if desired)
- Given contributor badge on GitHub

## Getting Started

Not sure where to start? Look for issues labeled:
- `good first issue` - Perfect for newcomers
- `help wanted` - We'd love your input
- `documentation` - Help improve docs

**Thank you for making FMU Gateway better!** 🚀

